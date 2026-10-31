
"""AutoPark - gerenciamento de estacionamento (Flask + MySQL)."""
import math
import os
import re
from datetime import date, datetime
from decimal import Decimal

import pymysql
from flask import Flask, flash, g, redirect, render_template, request, url_for
from jinja2 import DictLoader
from pymysql.cursors import DictCursor

DB_NAME = os.getenv("DB_NAME", "autopark")
CONN = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    charset="utf8mb4",
    cursorclass=DictCursor,
    autocommit=False,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "autopark-dev")


# ----------------------------------------------------------------- banco
def init_db():
    """Cria banco/tabelas (schema.sql) e semeia vagas na primeira execução."""
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "sql", "01_modelo_fisico.sql"), encoding="utf-8") as f:
        sql = f.read()
    sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    sql = sql.replace("autopark", DB_NAME)  # respeita DB_NAME definido no ambiente
    conn = pymysql.connect(**CONN)
    try:
        with conn.cursor() as cur:
            for stmt in (s.strip() for s in sql.split(";")):
                if stmt:
                    cur.execute(stmt)
            cur.execute("SELECT COUNT(*) AS n FROM tarifas")
            if cur.fetchone()["n"] == 0:
                cur.execute("""INSERT INTO tarifas (tipo_veiculo, tolerancia_min,
                               valor_primeira_hora, valor_hora_adicional, valor_diaria_max)
                               VALUES ('Carro',10,10.00,5.00,50.00),
                                      ('Moto',10,6.00,3.00,30.00),
                                      ('Utilitário',10,14.00,7.00,70.00)""")
            cur.execute("SELECT COUNT(*) AS n FROM vagas")
            if cur.fetchone()["n"] == 0:
                n = 1
                for setor, qtd, cat in (("A", 10, "Carro"), ("B", 10, "Carro"),
                                        ("C", 5, "Moto")):
                    for _ in range(qtd):
                        cur.execute("INSERT INTO vagas (numero_vaga, setor, categoria)"
                                    " VALUES (%s,%s,%s)", (n, setor, cat))
                        n += 1
                cur.execute("INSERT INTO vagas (numero_vaga, setor, categoria)"
                            " VALUES (%s,'A','PCD')", (n,))
        conn.commit()
    finally:
        conn.close()


def db():
    if "db" not in g:
        g.db = pymysql.connect(database=DB_NAME, **CONN)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def q(sql, args=(), one=False):
    with db().cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def ex(sql, args=()):
    with db().cursor() as cur:
        cur.execute(sql, args)
        return cur.lastrowid


# --------------------------------------------------------------- tarifa
def calcular_valor(entrada, saida, tipo_cliente, tipo_veiculo="Carro"):
    """Mensalista não paga por permanência. Avulso: tolerância, 1ª hora,
    horas adicionais (hora iniciada conta) e teto por diária de 24h,
    conforme a tarifa do tipo de veículo."""
    if tipo_cliente == "Mensalista":
        return Decimal("0.00")
    t = q("SELECT * FROM tarifas WHERE tipo_veiculo=%s", (tipo_veiculo,), one=True)
    minutos = max(0, int((saida - entrada).total_seconds() // 60))
    if minutos <= t["tolerancia_min"]:
        return Decimal("0.00")

    def por_horas(m):
        if m <= 0:
            return Decimal("0.00")
        horas = math.ceil(m / 60)
        v = t["valor_primeira_hora"] + (horas - 1) * t["valor_hora_adicional"]
        return min(v, t["valor_diaria_max"])

    dias, resto = divmod(minutos, 1440)
    return dias * t["valor_diaria_max"] + por_horas(resto)


def fmt_perm(minutos):
    return "%dh%02dmin" % divmod(int(minutos), 60)


@app.template_filter("dt")
def _dt(v):
    return v.strftime("%d/%m/%Y %H:%M") if v else "-"


@app.template_filter("brl")
def _brl(v):
    v = Decimal(v or 0)
    return "R$ {:,.2f}".format(v).replace(",", "X").replace(".", ",").replace("X", ".")


def normaliza_placa(p):
    return re.sub(r"[^A-Z0-9]", "", (p or "").upper())


# ---------------------------------------------------------------- rotas
@app.route("/")
def painel():
    vagas = q("""SELECT v.*, t.id_tiquete, t.placa, t.hora_entrada
                 FROM vagas v
                 LEFT JOIN tiquetes t ON t.numero_vaga = v.numero_vaga
                                     AND t.status = 'Aberto'
                 ORDER BY v.setor, v.numero_vaga""")
    agora = datetime.now()
    for v in vagas:
        if v["hora_entrada"]:
            v["perm"] = fmt_perm((agora - v["hora_entrada"]).total_seconds() // 60)
    livres = sum(1 for v in vagas if v["status"] == "Livre")
    hoje = q("""SELECT COALESCE(SUM(valor_calculado),0) AS total, COUNT(*) AS n
                FROM tiquetes WHERE status='Finalizado' AND DATE(hora_saida)=CURDATE()""",
             one=True)
    return render_template("painel.html", vagas=vagas, livres=livres,
                           ocupadas=len(vagas) - livres, total=len(vagas), hoje=hoje)


@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    if request.method == "POST":
        placa = normaliza_placa(request.form["placa"])
        if len(placa) < 6:
            flash("Placa inválida.", "erro")
            return redirect(url_for("entrada"))
        pcd = request.form.get("pcd") == "1"
        try:
            veic = q("SELECT * FROM veiculos WHERE placa=%s", (placa,), one=True)
            if not veic:
                nome = request.form.get("nome", "").strip() or "Avulso " + placa
                id_cli = ex("INSERT INTO clientes (nome, tipo) VALUES (%s,'Avulso')", (nome,))
                ex("""INSERT INTO veiculos (placa, modelo, cor, tipo_veiculo, id_cliente)
                      VALUES (%s,%s,%s,%s,%s)""",
                   (placa, request.form.get("modelo"), request.form.get("cor"),
                    request.form["tipo_veiculo"], id_cli))
                tipo_v = request.form["tipo_veiculo"]
            else:
                tipo_v = veic["tipo_veiculo"]
            if q("SELECT 1 FROM tiquetes WHERE placa=%s AND status='Aberto'", (placa,), one=True):
                db().rollback()
                flash("Este veículo já está no pátio com tíquete aberto.", "erro")
                return redirect(url_for("entrada"))
            categoria = "PCD" if pcd else ("Moto" if tipo_v == "Moto" else "Carro")
            vaga = q("""SELECT numero_vaga FROM vagas
                        WHERE status='Livre' AND categoria=%s
                        ORDER BY setor, numero_vaga LIMIT 1 FOR UPDATE""",
                     (categoria,), one=True)
            if not vaga:
                db().rollback()
                flash("Sem vagas livres na categoria %s." % categoria, "erro")
                return redirect(url_for("entrada"))
            ex("UPDATE vagas SET status='Ocupada' WHERE numero_vaga=%s", (vaga["numero_vaga"],))
            id_t = ex("""INSERT INTO tiquetes (placa, numero_vaga, hora_entrada)
                         VALUES (%s,%s,%s)""", (placa, vaga["numero_vaga"], datetime.now()))
            db().commit()
        except pymysql.err.IntegrityError:
            db().rollback()
            flash("Conflito ao registrar a entrada. Tente novamente.", "erro")
            return redirect(url_for("entrada"))
        return redirect(url_for("tiquete", id_tiquete=id_t))
    return render_template("entrada.html")


@app.route("/tiquete/<int:id_tiquete>")
def tiquete(id_tiquete):
    t = q("""SELECT t.*, v.modelo, v.cor, c.nome, c.tipo
             FROM tiquetes t JOIN veiculos v ON v.placa=t.placa
             JOIN clientes c ON c.id_cliente=v.id_cliente
             WHERE t.id_tiquete=%s""", (id_tiquete,), one=True)
    if not t:
        return "Tíquete não encontrado", 404
    return render_template("tiquete.html", t=t)


@app.route("/saida", methods=["GET", "POST"])
def saida():
    if request.method == "POST":
        placa = normaliza_placa(request.form["placa"])
        t = q("SELECT id_tiquete FROM tiquetes WHERE placa=%s AND status='Aberto'",
              (placa,), one=True)
        if not t:
            flash("Nenhum tíquete aberto para a placa %s." % placa, "erro")
            return redirect(url_for("saida"))
        return redirect(url_for("saida_confirma", id_tiquete=t["id_tiquete"]))
    abertos = q("""SELECT t.*, c.tipo FROM tiquetes t
                   JOIN veiculos v ON v.placa=t.placa
                   JOIN clientes c ON c.id_cliente=v.id_cliente
                   WHERE t.status='Aberto' ORDER BY t.hora_entrada""")
    return render_template("saida.html", abertos=abertos)


@app.route("/saida/<int:id_tiquete>", methods=["GET", "POST"])
def saida_confirma(id_tiquete):
    t = q("""SELECT t.*, c.nome, c.tipo, v.tipo_veiculo FROM tiquetes t
             JOIN veiculos v ON v.placa=t.placa
             JOIN clientes c ON c.id_cliente=v.id_cliente
             WHERE t.id_tiquete=%s""", (id_tiquete,), one=True)
    if not t or t["status"] != "Aberto":
        flash("Tíquete inexistente ou já finalizado.", "erro")
        return redirect(url_for("saida"))
    agora = datetime.now()
    valor = calcular_valor(t["hora_entrada"], agora, t["tipo"], t["tipo_veiculo"])
    perm = fmt_perm((agora - t["hora_entrada"]).total_seconds() // 60)
    if request.method == "POST":
        ex("""UPDATE tiquetes SET hora_saida=%s, valor_calculado=%s, status='Finalizado'
              WHERE id_tiquete=%s AND status='Aberto'""", (agora, valor, id_tiquete))
        ex("UPDATE vagas SET status='Livre' WHERE numero_vaga=%s", (t["numero_vaga"],))
        db().commit()
        flash("Saída registrada: %s em %s." % (_brl(valor), perm), "ok")
        return redirect(url_for("painel"))
    return render_template("saida_confirma.html", t=t, valor=valor, perm=perm, agora=agora)


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        try:
            ex("INSERT INTO clientes (nome, cpf, telefone, tipo) VALUES (%s,%s,%s,%s)",
               (request.form["nome"].strip(), request.form.get("cpf", "").strip() or None,
                request.form.get("telefone"), request.form["tipo"]))
            db().commit()
            flash("Cliente cadastrado.", "ok")
        except pymysql.err.IntegrityError:
            db().rollback()
            flash("CPF já cadastrado.", "erro")
        return redirect(url_for("clientes"))
    return render_template("clientes.html", lista=q("SELECT * FROM clientes ORDER BY nome"))


@app.route("/veiculos", methods=["GET", "POST"])
def veiculos():
    if request.method == "POST":
        try:
            ex("""INSERT INTO veiculos (placa, modelo, cor, tipo_veiculo, id_cliente)
                  VALUES (%s,%s,%s,%s,%s)""",
               (normaliza_placa(request.form["placa"]), request.form.get("modelo"),
                request.form.get("cor"), request.form["tipo_veiculo"],
                request.form["id_cliente"]))
            db().commit()
            flash("Veículo cadastrado.", "ok")
        except pymysql.err.IntegrityError:
            db().rollback()
            flash("Placa já cadastrada.", "erro")
        return redirect(url_for("veiculos"))
    lista = q("""SELECT v.*, c.nome, c.tipo FROM veiculos v
                 JOIN clientes c ON c.id_cliente=v.id_cliente ORDER BY v.placa""")
    return render_template("veiculos.html", lista=lista,
                           clientes=q("SELECT id_cliente, nome, tipo FROM clientes ORDER BY nome"))


@app.route("/vagas", methods=["GET", "POST"])
def vagas():
    if request.method == "POST":
        try:
            ex("INSERT INTO vagas (numero_vaga, setor, categoria) VALUES (%s,%s,%s)",
               (request.form["numero_vaga"], request.form["setor"].strip().upper(),
                request.form["categoria"]))
            db().commit()
            flash("Vaga cadastrada.", "ok")
        except pymysql.err.IntegrityError:
            db().rollback()
            flash("Número de vaga já existe.", "erro")
        return redirect(url_for("vagas"))
    return render_template("vagas.html", lista=q("SELECT * FROM vagas ORDER BY numero_vaga"))


@app.route("/caixa")
def caixa():
    dia = request.args.get("dia") or date.today().isoformat()
    lista = q("""SELECT t.*, c.tipo FROM tiquetes t
                 JOIN veiculos v ON v.placa=t.placa
                 JOIN clientes c ON c.id_cliente=v.id_cliente
                 WHERE t.status='Finalizado' AND DATE(t.hora_saida)=%s
                 ORDER BY t.hora_saida""", (dia,))
    total = sum((r["valor_calculado"] for r in lista), Decimal("0.00"))
    return render_template("caixa.html", lista=lista, total=total, dia=dia)


# ------------------------------------------------------------ templates
BASE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AutoPark</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#1c2530;--mut:#6b7785;--pri:#0b5fff;--ok:#12805c;--err:#c62828;--bd:#dde3ea}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--ink)}
nav{background:#101a2b;display:flex;gap:4px;padding:0 16px;align-items:center;flex-wrap:wrap}
nav b{color:#fff;margin-right:16px;padding:14px 0}nav a{color:#c9d3e3;text-decoration:none;padding:14px 12px}
nav a:hover{background:#1b2a45;color:#fff}main{max-width:1100px;margin:20px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-bottom:16px}
h1,h2{margin:0 0 12px}h1{font-size:1.4rem}h2{font-size:1.1rem}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--bd);font-size:.92rem}
th{color:var(--mut);font-weight:600}
form.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;align-items:end}
label{display:flex;flex-direction:column;font-size:.8rem;color:var(--mut);gap:4px}
input,select{padding:9px;border:1px solid var(--bd);border-radius:6px;font-size:1rem}
button,.btn{background:var(--pri);color:#fff;border:0;padding:10px 16px;border-radius:6px;font-size:1rem;cursor:pointer;text-decoration:none;display:inline-block}
.btn.sec{background:#e8edf4;color:var(--ink)}
.msg{padding:10px 14px;border-radius:6px;margin-bottom:12px}.msg.ok{background:#dff5ec;color:var(--ok)}.msg.erro{background:#fde7e7;color:var(--err)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px}.kpi small{color:var(--mut)}.kpi div{font-size:1.6rem;font-weight:700}
.vagas{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}
.vaga{border-radius:8px;padding:10px;border:2px solid var(--ok);background:#effaf5;font-size:.85rem}
.vaga.oc{border-color:var(--err);background:#fdf0f0}.vaga b{font-size:1.05rem}
.big{font-size:2.2rem;font-weight:800}.placa{font-family:monospace;font-weight:700;letter-spacing:1px}
@media print{nav,.noprint{display:none}}
</style></head><body>
<nav><b>🅿 AutoPark</b><a href="/">Painel</a><a href="/entrada">Entrada</a><a href="/saida">Saída</a>
<a href="/clientes">Clientes</a><a href="/veiculos">Veículos</a><a href="/vagas">Vagas</a><a href="/caixa">Caixa</a></nav>
<main>{% for cat,m in get_flashed_messages(with_categories=true) %}<div class="msg {{cat}}">{{m}}</div>{% endfor %}
{% block c %}{% endblock %}</main></body></html>"""

T = {"base.html": BASE}

T["painel.html"] = """{% extends "base.html" %}{% block c %}
<div class="kpis">
<div class="kpi"><small>Vagas livres</small><div style="color:var(--ok)">{{livres}}</div></div>
<div class="kpi"><small>Ocupadas</small><div style="color:var(--err)">{{ocupadas}}</div></div>
<div class="kpi"><small>Total de vagas</small><div>{{total}}</div></div>
<div class="kpi"><small>Faturado hoje ({{hoje.n}} saídas)</small><div>{{hoje.total|brl}}</div></div></div>
<div class="card"><h2>Mapa do pátio</h2><div class="vagas">
{% for v in vagas %}<div class="vaga {{'oc' if v.status=='Ocupada'}}"><b>{{v.numero_vaga}}</b> · {{v.setor}} · {{v.categoria}}<br>
{% if v.placa %}<a class="placa" href="/saida/{{v.id_tiquete}}">{{v.placa}}</a><br><small>{{v.perm}}</small>{% else %}Livre{% endif %}</div>{% endfor %}
</div></div>{% endblock %}"""

T["entrada.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Registrar entrada</h1>
<form class="grid" method="post">
<label>Placa<input name="placa" required maxlength="10" autofocus style="text-transform:uppercase"></label>
<label>Tipo de veículo<select name="tipo_veiculo"><option>Carro</option><option>Moto</option><option>Utilitário</option></select></label>
<label>Modelo<input name="modelo"></label><label>Cor<input name="cor"></label>
<label>Nome (opcional)<input name="nome"></label>
<label>Vaga PCD?<select name="pcd"><option value="0">Não</option><option value="1">Sim</option></select></label>
<button>Gerar tíquete</button></form>
<p style="color:var(--mut);font-size:.85rem">Placas já cadastradas (inclusive mensalistas) são reconhecidas automaticamente; modelo, cor e tipo só valem para placas novas.</p></div>{% endblock %}"""

T["tiquete.html"] = """{% extends "base.html" %}{% block c %}
<div class="card" style="max-width:420px"><h1>Tíquete #{{t.id_tiquete}}</h1>
<div class="placa big">{{t.placa}}</div>
<p>{{t.modelo or ''}} {{t.cor or ''}}<br>Cliente: {{t.nome}} ({{t.tipo}})<br>
Vaga: <b>{{t.numero_vaga}}</b><br>Entrada: {{t.hora_entrada|dt}}
{% if t.hora_saida %}<br>Saída: {{t.hora_saida|dt}}<br>Valor: <b>{{t.valor_calculado|brl}}</b>{% endif %}</p>
<p class="noprint"><button onclick="window.print()">Imprimir</button> <a class="btn sec" href="/">Painel</a></p></div>{% endblock %}"""

T["saida.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Registrar saída</h1>
<form class="grid" method="post"><label>Placa<input name="placa" required autofocus style="text-transform:uppercase"></label>
<button>Calcular</button></form></div>
<div class="card"><h2>Veículos no pátio</h2><table><tr><th>Tíquete</th><th>Placa</th><th>Vaga</th><th>Entrada</th><th>Tipo</th><th></th></tr>
{% for t in abertos %}<tr><td>#{{t.id_tiquete}}</td><td class="placa">{{t.placa}}</td><td>{{t.numero_vaga}}</td><td>{{t.hora_entrada|dt}}</td><td>{{t.tipo}}</td>
<td><a class="btn sec" href="/saida/{{t.id_tiquete}}">Saída</a></td></tr>{% else %}<tr><td colspan="6">Pátio vazio.</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["saida_confirma.html"] = """{% extends "base.html" %}{% block c %}
<div class="card" style="max-width:460px"><h1>Confirmar saída</h1>
<div class="placa big">{{t.placa}}</div>
<p>Cliente: {{t.nome}} ({{t.tipo}})<br>Vaga {{t.numero_vaga}}<br>Entrada: {{t.hora_entrada|dt}}<br>Saída: {{agora|dt}}<br>Permanência: <b>{{perm}}</b></p>
<div class="big">{{valor|brl}}</div>{% if t.tipo=='Mensalista' %}<small>Mensalista: sem cobrança por permanência.</small>{% endif %}
<form method="post" style="margin-top:14px"><button>Receber e liberar vaga</button> <a class="btn sec" href="/saida">Voltar</a></form></div>{% endblock %}"""

T["clientes.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Novo cliente</h1><form class="grid" method="post">
<label>Nome<input name="nome" required></label><label>CPF<input name="cpf" maxlength="14"></label>
<label>Telefone<input name="telefone"></label>
<label>Tipo<select name="tipo"><option>Mensalista</option><option>Avulso</option></select></label><button>Salvar</button></form></div>
<div class="card"><table><tr><th>ID</th><th>Nome</th><th>CPF</th><th>Telefone</th><th>Tipo</th></tr>
{% for c in lista %}<tr><td>{{c.id_cliente}}</td><td>{{c.nome}}</td><td>{{c.cpf or ''}}</td><td>{{c.telefone or ''}}</td><td>{{c.tipo}}</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["veiculos.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Novo veículo</h1><form class="grid" method="post">
<label>Placa<input name="placa" required maxlength="10" style="text-transform:uppercase"></label>
<label>Modelo<input name="modelo"></label><label>Cor<input name="cor"></label>
<label>Tipo<select name="tipo_veiculo"><option>Carro</option><option>Moto</option><option>Utilitário</option></select></label>
<label>Proprietário<select name="id_cliente">{% for c in clientes %}<option value="{{c.id_cliente}}">{{c.nome}} ({{c.tipo}})</option>{% endfor %}</select></label>
<button>Salvar</button></form></div>
<div class="card"><table><tr><th>Placa</th><th>Modelo</th><th>Cor</th><th>Tipo</th><th>Proprietário</th></tr>
{% for v in lista %}<tr><td class="placa">{{v.placa}}</td><td>{{v.modelo or ''}}</td><td>{{v.cor or ''}}</td><td>{{v.tipo_veiculo}}</td><td>{{v.nome}} ({{v.tipo}})</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["vagas.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Nova vaga</h1><form class="grid" method="post">
<label>Número<input name="numero_vaga" type="number" required></label><label>Setor<input name="setor" required maxlength="20"></label>
<label>Categoria<select name="categoria"><option>Carro</option><option>Moto</option><option>PCD</option></select></label><button>Salvar</button></form></div>
<div class="card"><table><tr><th>Nº</th><th>Setor</th><th>Categoria</th><th>Status</th></tr>
{% for v in lista %}<tr><td>{{v.numero_vaga}}</td><td>{{v.setor}}</td><td>{{v.categoria}}</td><td>{{v.status}}</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["caixa.html"] = """{% extends "base.html" %}{% block c %}
<div class="card"><h1>Fechamento de caixa</h1><form class="grid" method="get"><label>Dia<input type="date" name="dia" value="{{dia}}"></label><button>Filtrar</button></form></div>
<div class="kpis"><div class="kpi"><small>Total do dia</small><div>{{total|brl}}</div></div><div class="kpi"><small>Saídas</small><div>{{lista|length}}</div></div></div>
<div class="card"><table><tr><th>Tíquete</th><th>Placa</th><th>Tipo</th><th>Entrada</th><th>Saída</th><th>Valor</th></tr>
{% for t in lista %}<tr><td>#{{t.id_tiquete}}</td><td class="placa">{{t.placa}}</td><td>{{t.tipo}}</td><td>{{t.hora_entrada|dt}}</td><td>{{t.hora_saida|dt}}</td><td>{{t.valor_calculado|brl}}</td></tr>
{% else %}<tr><td colspan="6">Sem movimento nesta data.</td></tr>{% endfor %}</table></div>{% endblock %}"""

app.jinja_loader = DictLoader(T)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
