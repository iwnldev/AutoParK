-- ============================================================================
-- AutoPark - 10 CONSULTAS
-- Recursos: funções de agregação, GROUP BY, HAVING, JOIN, LIKE e BETWEEN
-- Executar depois de 01_modelo_fisico.sql e 02_dados.sql
-- ============================================================================

USE autopark;

-- Consulta 1
-- Recurso: Agregação (COUNT) + GROUP BY
-- Enunciado: Quantos clientes existem de cada tipo (Mensalista ou Avulso)?
SELECT tipo, COUNT(*) AS total_clientes
FROM clientes
GROUP BY tipo
ORDER BY total_clientes DESC;

-- Consulta 2
-- Recurso: Funções de agregação (COUNT, SUM, AVG, MIN, MAX) + TIMESTAMPDIFF
-- Enunciado: Qual o resumo financeiro dos tíquetes finalizados (quantidade, total, média, menor e maior valor) e a permanência média em minutos?
SELECT COUNT(*) AS qtd_saidas,
       SUM(valor_calculado) AS total_arrecadado,
       ROUND(AVG(valor_calculado), 2) AS valor_medio,
       MIN(valor_calculado) AS menor_valor,
       MAX(valor_calculado) AS maior_valor,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, hora_entrada, hora_saida)), 2) AS permanencia_media_min
FROM tiquetes
WHERE status = 'Finalizado';

-- Consulta 3
-- Recurso: JOIN (LEFT JOIN)
-- Enunciado: Qual a situação atual de cada vaga e, quando ocupada, qual placa está nela?
SELECT va.numero_vaga, va.setor, va.categoria, va.status, t.placa, t.hora_entrada
FROM vagas va
LEFT JOIN tiquetes t ON t.numero_vaga = va.numero_vaga AND t.status = 'Aberto'
ORDER BY va.numero_vaga;

-- Consulta 4
-- Recurso: LIKE
-- Enunciado: Quais clientes têm "Souza" no nome?
SELECT id_cliente, nome, cpf, tipo
FROM clientes
WHERE nome LIKE '%Souza%';

-- Consulta 5
-- Recurso: JOIN + LIKE
-- Enunciado: Quais veículos têm modelo iniciado por "H" ou por "O" e quem é o proprietário de cada um?
SELECT v.placa, v.modelo, v.cor, c.nome AS proprietario
FROM veiculos v
JOIN clientes c ON c.id_cliente = v.id_cliente
WHERE v.modelo LIKE 'H%' OR v.modelo LIKE 'O%'
ORDER BY v.placa;

-- Consulta 6
-- Recurso: BETWEEN (valores)
-- Enunciado: Quais tíquetes tiveram valor cobrado entre R$ 10,00 e R$ 20,00?
SELECT id_tiquete, placa, valor_calculado
FROM tiquetes
WHERE valor_calculado BETWEEN 10 AND 20;

-- Consulta 7
-- Recurso: JOIN de 3 tabelas + BETWEEN (datas)
-- Enunciado: Quais tíquetes tiveram entrada durante o dia 30/10/2026, com nome do cliente e placa?
SELECT t.id_tiquete, c.nome, v.placa, t.hora_entrada, t.hora_saida, t.status
FROM tiquetes t
JOIN veiculos v ON v.placa = t.placa
JOIN clientes c ON c.id_cliente = v.id_cliente
WHERE t.hora_entrada BETWEEN '2026-10-30 00:00:00' AND '2026-10-30 23:59:59'
ORDER BY t.hora_entrada;

-- Consulta 8
-- Recurso: GROUP BY + HAVING
-- Enunciado: Quais categorias de vaga possuem 2 ou mais vagas cadastradas?
SELECT categoria, COUNT(*) AS qtd_vagas
FROM vagas
GROUP BY categoria
HAVING COUNT(*) >= 2;

-- Consulta 9
-- Recurso: JOIN + GROUP BY + SUM
-- Enunciado: Qual o faturamento e a quantidade de saídas por tipo de veículo?
SELECT v.tipo_veiculo, COUNT(*) AS qtd_saidas, SUM(t.valor_calculado) AS faturamento
FROM tiquetes t
JOIN veiculos v ON v.placa = t.placa
WHERE t.status = 'Finalizado'
GROUP BY v.tipo_veiculo
ORDER BY faturamento DESC;

-- Consulta 10
-- Recurso: JOIN de 3 tabelas + GROUP BY + HAVING
-- Enunciado: Quais clientes já pagaram mais de R$ 20,00 em estacionamento, com quantidade de tíquetes e total pago?
SELECT c.nome, c.tipo, COUNT(t.id_tiquete) AS qtd_tiquetes, SUM(t.valor_calculado) AS total_pago
FROM clientes c
JOIN veiculos v ON v.id_cliente = c.id_cliente
JOIN tiquetes t ON t.placa = v.placa
GROUP BY c.id_cliente, c.nome, c.tipo
HAVING SUM(t.valor_calculado) > 20;
