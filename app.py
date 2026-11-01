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
# O visual fica em static/autopark.css (o mesmo arquivo serve o PHP em php/autopark.css).
BASE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AutoPark</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap">
<link rel="stylesheet" href="{{ url_for('static', filename='autopark.css') }}">
</head><body>
{% set ep = request.endpoint %}
<header class="top"><div class="top-in">
<a class="brand" href="{{ url_for('painel') }}"><span class="brand-p">P</span>AutoPark</a>
<nav class="nav" aria-label="Principal">
<a href="{{ url_for('painel') }}" {% if ep == 'painel' %}aria-current="page"{% endif %}>Painel</a>
<a href="{{ url_for('entrada') }}" {% if ep == 'entrada' %}aria-current="page"{% endif %}>Entrada</a>
<a href="{{ url_for('saida') }}" {% if ep in ('saida', 'saida_confirma') %}aria-current="page"{% endif %}>Saída</a>
<a href="{{ url_for('clientes') }}" {% if ep == 'clientes' %}aria-current="page"{% endif %}>Clientes</a>
<a href="{{ url_for('veiculos') }}" {% if ep == 'veiculos' %}aria-current="page"{% endif %}>Veículos</a>
<a href="{{ url_for('vagas') }}" {% if ep == 'vagas' %}aria-current="page"{% endif %}>Vagas</a>
<a href="{{ url_for('caixa') }}" {% if ep == 'caixa' %}aria-current="page"{% endif %}>Caixa</a>
</nav></div></header>
<main class="wrap">
{% for cat, m in get_flashed_messages(with_categories=true) %}<div class="msg {{ cat }}" role="status">{{ m }}</div>{% endfor %}
{% block c %}{% endblock %}
</main></body></html>"""

T = {"base.html": BASE}

T["painel.html"] = """{% extends "base.html" %}{% block c %}
{% set pct = ((ocupadas * 100 / total)|round|int) if total else 0 %}
<div class="summary">
<section class="panel">
<p class="big">{{ livres }}<small>vagas livres de {{ total }}</small></p>
<div class="meter" role="img" aria-label="{{ pct }}% do pátio ocupado"><span style="width:{{ pct }}%"></span></div>
<p class="muted" style="margin:0">{{ ocupadas }} ocupadas, {{ pct }}% do pátio</p>
</section>
<section class="panel">
<p class="muted" style="margin:0">Caixa de hoje</p>
<p class="big">{{ hoje.total|brl }}</p>
<p class="muted" style="margin:6px 0 14px">{{ hoje.n }} {{ 'saída' if hoje.n == 1 else 'saídas' }}</p>
<a class="btn sec small" href="{{ url_for('caixa') }}">Ver caixa do dia</a>
</section>
</div>
<section class="lot">
<h2>Pátio agora</h2>
<p class="hint">Toque numa vaga ocupada para dar saída ao veículo.</p>
{% for setor, itens in vagas|groupby('setor') %}
<div class="sector">
<div class="sector-title"><h3>Setor {{ setor }}</h3>
<span>{{ itens|selectattr('status', 'equalto', 'Livre')|list|length }} livres de {{ itens|length }}</span></div>
<div class="bays">
{% for v in itens %}
{% if v.placa %}
<a class="bay busy" href="{{ url_for('saida_confirma', id_tiquete=v.id_tiquete) }}" aria-label="Vaga {{ v.numero_vaga }}, placa {{ v.placa }}, ocupada há {{ v.perm }}. Dar saída.">
<span class="bay-no">{{ v.numero_vaga }}</span>{% if v.categoria != 'Carro' %}<span class="bay-cat">{{ v.categoria }}</span>{% endif %}
<span class="plate">{{ v.placa }}</span><span class="bay-time">{{ v.perm }}</span></a>
{% else %}
<div class="bay free"><span class="bay-no">{{ v.numero_vaga }}</span>{% if v.categoria != 'Carro' %}<span class="bay-cat">{{ v.categoria }}</span>{% endif %}
<span class="bay-state">Livre</span></div>
{% endif %}
{% endfor %}
</div></div>
{% endfor %}
</section>{% endblock %}"""

T["entrada.html"] = """{% extends "base.html" %}{% block c %}
<h1>Registrar entrada</h1>
<form method="post" class="panel">
<div class="plate-field">
<label for="placa">Placa do veículo</label>
<input id="placa" class="plate-input" name="placa" required maxlength="8" autofocus autocomplete="off" placeholder="ABC1D23">
</div>
<h2 style="margin-top:26px">Dados do veículo</h2>
<p class="hint" style="margin:0 0 14px">Só são usados quando a placa ainda não está cadastrada. Mensalistas e clientes antigos são reconhecidos pela placa.</p>
<div class="form-grid">
<label>Tipo de veículo<select name="tipo_veiculo"><option>Carro</option><option>Moto</option><option>Utilitário</option></select></label>
<label>Modelo<input name="modelo" maxlength="60"></label>
<label>Cor<input name="cor" maxlength="30"></label>
<label>Nome do cliente (opcional)<input name="nome" maxlength="120"></label>
<label class="check"><input type="checkbox" name="pcd" value="1"> Vaga PCD</label>
</div>
<p style="margin:22px 0 0"><button type="submit">Gerar tíquete</button></p>
</form>{% endblock %}"""

T["tiquete.html"] = """{% extends "base.html" %}{% block c %}
<div class="ticket">
<h1>Tíquete {{ t.id_tiquete }}</h1>
<span class="plate lg">{{ t.placa }}</span>
<dl class="facts">
<dt>Veículo</dt><dd>{{ t.modelo or '-' }}{% if t.cor %}, {{ t.cor }}{% endif %}</dd>
<dt>Cliente</dt><dd>{{ t.nome }} <span class="chip {{ t.tipo|lower }}">{{ t.tipo }}</span></dd>
<dt>Vaga</dt><dd>{{ t.numero_vaga }}</dd>
<dt>Entrada</dt><dd>{{ t.hora_entrada|dt }}</dd>
{% if t.hora_saida %}<dt>Saída</dt><dd>{{ t.hora_saida|dt }}</dd><dt>Valor</dt><dd>{{ t.valor_calculado|brl }}</dd>{% endif %}
</dl>
<p class="noprint" style="margin:18px 0 0"><button type="button" onclick="window.print()">Imprimir tíquete</button>
<a class="btn sec" href="{{ url_for('painel') }}">Voltar ao painel</a></p>
</div>{% endblock %}"""

T["saida.html"] = """{% extends "base.html" %}{% block c %}
<h1>Registrar saída</h1>
<form method="post" class="panel">
<div class="plate-field">
<label for="placa">Placa do veículo</label>
<input id="placa" class="plate-input" name="placa" required maxlength="8" autofocus autocomplete="off" placeholder="ABC1D23">
<button type="submit">Calcular valor</button>
</div></form>
<section class="panel"><h2>Veículos no pátio</h2>
<div class="table-wrap"><table>
<thead><tr><th>Tíquete</th><th>Placa</th><th>Vaga</th><th>Entrada</th><th>Cliente</th><th></th></tr></thead>
<tbody>
{% for t in abertos %}<tr><td>{{ t.id_tiquete }}</td><td><span class="plate">{{ t.placa }}</span></td><td>{{ t.numero_vaga }}</td>
<td>{{ t.hora_entrada|dt }}</td><td><span class="chip {{ t.tipo|lower }}">{{ t.tipo }}</span></td>
<td class="num"><a class="btn sec small" href="{{ url_for('saida_confirma', id_tiquete=t.id_tiquete) }}">Dar saída</a></td></tr>
{% else %}<tr><td colspan="6" class="empty">Nenhum veículo no pátio.</td></tr>{% endfor %}
</tbody></table></div></section>{% endblock %}"""

T["saida_confirma.html"] = """{% extends "base.html" %}{% block c %}
<h1>Confirmar saída</h1>
<div class="split">
<section class="panel">
<span class="plate lg">{{ t.placa }}</span>
<dl class="facts">
<dt>Cliente</dt><dd>{{ t.nome }} <span class="chip {{ t.tipo|lower }}">{{ t.tipo }}</span></dd>
<dt>Vaga</dt><dd>{{ t.numero_vaga }}</dd>
<dt>Entrada</dt><dd>{{ t.hora_entrada|dt }}</dd>
<dt>Saída</dt><dd>{{ agora|dt }}</dd>
<dt>Permanência</dt><dd>{{ perm }}</dd>
</dl></section>
<section class="total">
<p class="label">Valor a receber</p>
<p class="big">{{ valor|brl }}</p>
{% if t.tipo == 'Mensalista' %}<p class="note">Mensalista: sem cobrança por permanência.</p>{% endif %}
<form method="post" class="actions"><button type="submit">Receber e liberar vaga</button>
<a class="btn sec" href="{{ url_for('saida') }}">Voltar</a></form>
</section></div>{% endblock %}"""

T["clientes.html"] = """{% extends "base.html" %}{% block c %}
<h1>Clientes</h1>
<form method="post" class="panel"><h2>Novo cliente</h2>
<div class="form-grid">
<label>Nome<input name="nome" required maxlength="120"></label>
<label>CPF<input name="cpf" maxlength="14" placeholder="000.000.000-00"></label>
<label>Telefone<input name="telefone" maxlength="20"></label>
<label>Tipo<select name="tipo"><option>Avulso</option><option>Mensalista</option></select></label>
<button type="submit">Salvar cliente</button></div></form>
<section class="panel"><div class="table-wrap"><table>
<thead><tr><th>ID</th><th>Nome</th><th>CPF</th><th>Telefone</th><th>Tipo</th></tr></thead><tbody>
{% for c in lista %}<tr><td>{{ c.id_cliente }}</td><td>{{ c.nome }}</td><td>{{ c.cpf or '' }}</td><td>{{ c.telefone or '' }}</td>
<td><span class="chip {{ c.tipo|lower }}">{{ c.tipo }}</span></td></tr>
{% else %}<tr><td colspan="5" class="empty">Nenhum cliente cadastrado.</td></tr>{% endfor %}
</tbody></table></div></section>{% endblock %}"""

T["veiculos.html"] = """{% extends "base.html" %}{% block c %}
<h1>Veículos</h1>
<form method="post" class="panel"><h2>Novo veículo</h2>
<div class="form-grid">
<label>Placa<input name="placa" required maxlength="10" style="text-transform:uppercase"></label>
<label>Modelo<input name="modelo" maxlength="60"></label>
<label>Cor<input name="cor" maxlength="30"></label>
<label>Tipo<select name="tipo_veiculo"><option>Carro</option><option>Moto</option><option>Utilitário</option></select></label>
<label>Proprietário<select name="id_cliente">{% for c in clientes %}<option value="{{ c.id_cliente }}">{{ c.nome }} ({{ c.tipo }})</option>{% endfor %}</select></label>
<button type="submit">Salvar veículo</button></div></form>
<section class="panel"><div class="table-wrap"><table>
<thead><tr><th>Placa</th><th>Modelo</th><th>Cor</th><th>Tipo</th><th>Proprietário</th></tr></thead><tbody>
{% for v in lista %}<tr><td><span class="plate">{{ v.placa }}</span></td><td>{{ v.modelo or '' }}</td><td>{{ v.cor or '' }}</td><td>{{ v.tipo_veiculo }}</td>
<td>{{ v.nome }} <span class="chip {{ v.tipo|lower }}">{{ v.tipo }}</span></td></tr>
{% else %}<tr><td colspan="5" class="empty">Nenhum veículo cadastrado.</td></tr>{% endfor %}
</tbody></table></div></section>{% endblock %}"""

T["vagas.html"] = """{% extends "base.html" %}{% block c %}
<h1>Vagas</h1>
<form method="post" class="panel"><h2>Nova vaga</h2>
<div class="form-grid">
<label>Número<input name="numero_vaga" type="number" min="1" required></label>
<label>Setor<input name="setor" required maxlength="20"></label>
<label>Categoria<select name="categoria"><option>Carro</option><option>Moto</option><option>PCD</option></select></label>
<button type="submit">Salvar vaga</button></div></form>
<section class="panel"><div class="table-wrap"><table>
<thead><tr><th>Número</th><th>Setor</th><th>Categoria</th><th>Situação</th></tr></thead><tbody>
{% for v in lista %}<tr><td>{{ v.numero_vaga }}</td><td>{{ v.setor }}</td><td>{{ v.categoria }}</td><td>{{ v.status }}</td></tr>
{% else %}<tr><td colspan="4" class="empty">Nenhuma vaga cadastrada.</td></tr>{% endfor %}
</tbody></table></div></section>{% endblock %}"""

T["caixa.html"] = """{% extends "base.html" %}{% block c %}
<h1>Caixa</h1>
<div class="summary">
<form method="get" class="panel"><div class="form-grid">
<label>Dia<input type="date" name="dia" value="{{ dia }}"></label><button type="submit">Ver dia</button></div></form>
<section class="panel"><p class="muted" style="margin:0">Total do dia, {{ lista|length }} {{ 'saída' if lista|length == 1 else 'saídas' }}</p>
<p class="big">{{ total|brl }}</p></section></div>
<section class="panel"><div class="table-wrap"><table>
<thead><tr><th>Tíquete</th><th>Placa</th><th>Cliente</th><th>Entrada</th><th>Saída</th><th class="num">Valor</th></tr></thead><tbody>
{% for t in lista %}<tr><td>{{ t.id_tiquete }}</td><td><span class="plate">{{ t.placa }}</span></td>
<td><span class="chip {{ t.tipo|lower }}">{{ t.tipo }}</span></td><td>{{ t.hora_entrada|dt }}</td><td>{{ t.hora_saida|dt }}</td>
<td class="num">{{ t.valor_calculado|brl }}</td></tr>
{% else %}<tr><td colspan="6" class="empty">Nenhuma saída neste dia.</td></tr>{% endfor %}
</tbody>
{% if lista %}<tfoot><tr><td colspan="5">Total</td><td class="num">{{ total|brl }}</td></tr></tfoot>{% endif %}
</table></div></section>{% endblock %}"""

app.jinja_loader = DictLoader(T)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
