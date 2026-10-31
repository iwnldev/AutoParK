# AutoPark — 10 consultas com enunciado, código SQL e resultado

Base de dados: `sql/01_modelo_fisico.sql` + `sql/02_dados.sql` (3 linhas por tabela).

## Consulta 1 — Agregação (COUNT) + GROUP BY

**Enunciado:** Quantos clientes existem de cada tipo (Mensalista ou Avulso)?

```sql
SELECT tipo, COUNT(*) AS total_clientes
FROM clientes
GROUP BY tipo
ORDER BY total_clientes DESC;
```

**Resultado:**

| tipo | total_clientes |
|---|---|
| Avulso | 2 |
| Mensalista | 1 |

_2 linha(s)._

## Consulta 2 — Funções de agregação (COUNT, SUM, AVG, MIN, MAX) + TIMESTAMPDIFF

**Enunciado:** Qual o resumo financeiro dos tíquetes finalizados (quantidade, total, média, menor e maior valor) e a permanência média em minutos?

```sql
SELECT COUNT(*) AS qtd_saidas,
       SUM(valor_calculado) AS total_arrecadado,
       ROUND(AVG(valor_calculado), 2) AS valor_medio,
       MIN(valor_calculado) AS menor_valor,
       MAX(valor_calculado) AS maior_valor,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, hora_entrada, hora_saida)), 2) AS permanencia_media_min
FROM tiquetes
WHERE status = 'Finalizado';
```

**Resultado:**

| qtd_saidas | total_arrecadado | valor_medio | menor_valor | maior_valor | permanencia_media_min |
|---|---|---|---|---|---|
| 2 | 40.00 | 20.00 | 15.00 | 25.00 | 202.50 |

_1 linha(s)._

## Consulta 3 — JOIN (LEFT JOIN)

**Enunciado:** Qual a situação atual de cada vaga e, quando ocupada, qual placa está nela?

```sql
SELECT va.numero_vaga, va.setor, va.categoria, va.status, t.placa, t.hora_entrada
FROM vagas va
LEFT JOIN tiquetes t ON t.numero_vaga = va.numero_vaga AND t.status = 'Aberto'
ORDER BY va.numero_vaga;
```

**Resultado:**

| numero_vaga | setor | categoria | status | placa | hora_entrada |
|---|---|---|---|---|---|
| 1 | A | Carro | Livre | NULL | NULL |
| 2 | B | Moto | Livre | NULL | NULL |
| 3 | A | Carro | Ocupada | HIJ7K89 | 2026-10-31 07:50:00 |

_3 linha(s)._

## Consulta 4 — LIKE

**Enunciado:** Quais clientes têm "Souza" no nome?

```sql
SELECT id_cliente, nome, cpf, tipo
FROM clientes
WHERE nome LIKE '%Souza%';
```

**Resultado:**

| id_cliente | nome | cpf | tipo |
|---|---|---|---|
| 1 | Carlos Henrique Souza | 111.222.333-44 | Avulso |

_1 linha(s)._

## Consulta 5 — JOIN + LIKE

**Enunciado:** Quais veículos têm modelo iniciado por "H" ou por "O" e quem é o proprietário de cada um?

```sql
SELECT v.placa, v.modelo, v.cor, c.nome AS proprietario
FROM veiculos v
JOIN clientes c ON c.id_cliente = v.id_cliente
WHERE v.modelo LIKE 'H%' OR v.modelo LIKE 'O%'
ORDER BY v.placa;
```

**Resultado:**

| placa | modelo | cor | proprietario |
|---|---|---|---|
| ABC1D23 | Onix | Prata | Carlos Henrique Souza |
| HIJ7K89 | Hilux | Preta | Marcos Vinícius Lima |

_2 linha(s)._

## Consulta 6 — BETWEEN (valores)

**Enunciado:** Quais tíquetes tiveram valor cobrado entre R$ 10,00 e R$ 20,00?

```sql
SELECT id_tiquete, placa, valor_calculado
FROM tiquetes
WHERE valor_calculado BETWEEN 10 AND 20;
```

**Resultado:**

| id_tiquete | placa | valor_calculado |
|---|---|---|
| 2 | DEF4G56 | 15.00 |

_1 linha(s)._

## Consulta 7 — JOIN de 3 tabelas + BETWEEN (datas)

**Enunciado:** Quais tíquetes tiveram entrada durante o dia 30/10/2026, com nome do cliente e placa?

```sql
SELECT t.id_tiquete, c.nome, v.placa, t.hora_entrada, t.hora_saida, t.status
FROM tiquetes t
JOIN veiculos v ON v.placa = t.placa
JOIN clientes c ON c.id_cliente = v.id_cliente
WHERE t.hora_entrada BETWEEN '2026-10-30 00:00:00' AND '2026-10-30 23:59:59'
ORDER BY t.hora_entrada;
```

**Resultado:**

| id_tiquete | nome | placa | hora_entrada | hora_saida | status |
|---|---|---|---|---|---|
| 1 | Carlos Henrique Souza | ABC1D23 | 2026-10-30 08:00:00 | 2026-10-30 11:20:00 | Finalizado |
| 2 | Ana Paula Ribeiro | DEF4G56 | 2026-10-30 09:15:00 | 2026-10-30 12:40:00 | Finalizado |

_2 linha(s)._

## Consulta 8 — GROUP BY + HAVING

**Enunciado:** Quais categorias de vaga possuem 2 ou mais vagas cadastradas?

```sql
SELECT categoria, COUNT(*) AS qtd_vagas
FROM vagas
GROUP BY categoria
HAVING COUNT(*) >= 2;
```

**Resultado:**

| categoria | qtd_vagas |
|---|---|
| Carro | 2 |

_1 linha(s)._

## Consulta 9 — JOIN + GROUP BY + SUM

**Enunciado:** Qual o faturamento e a quantidade de saídas por tipo de veículo?

```sql
SELECT v.tipo_veiculo, COUNT(*) AS qtd_saidas, SUM(t.valor_calculado) AS faturamento
FROM tiquetes t
JOIN veiculos v ON v.placa = t.placa
WHERE t.status = 'Finalizado'
GROUP BY v.tipo_veiculo
ORDER BY faturamento DESC;
```

**Resultado:**

| tipo_veiculo | qtd_saidas | faturamento |
|---|---|---|
| Carro | 1 | 25.00 |
| Moto | 1 | 15.00 |

_2 linha(s)._

## Consulta 10 — JOIN de 3 tabelas + GROUP BY + HAVING

**Enunciado:** Quais clientes já pagaram mais de R$ 20,00 em estacionamento, com quantidade de tíquetes e total pago?

```sql
SELECT c.nome, c.tipo, COUNT(t.id_tiquete) AS qtd_tiquetes, SUM(t.valor_calculado) AS total_pago
FROM clientes c
JOIN veiculos v ON v.id_cliente = c.id_cliente
JOIN tiquetes t ON t.placa = v.placa
GROUP BY c.id_cliente, c.nome, c.tipo
HAVING SUM(t.valor_calculado) > 20;
```

**Resultado:**

| nome | tipo | qtd_tiquetes | total_pago |
|---|---|---|---|
| Carlos Henrique Souza | Avulso | 1 | 25.00 |

_1 linha(s)._
