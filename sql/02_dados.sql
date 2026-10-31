-- ============================================================================
-- AutoPark - CARGA DE DADOS (3 linhas por tabela)
-- Executar depois de 01_modelo_fisico.sql
-- ============================================================================

USE autopark;

-- TARIFAS (3 linhas)
INSERT INTO tarifas (tipo_veiculo, tolerancia_min, valor_primeira_hora, valor_hora_adicional, valor_diaria_max) VALUES
('Carro',      10, 10.00, 5.00, 50.00),
('Moto',       10,  6.00, 3.00, 30.00),
('Utilitário', 10, 14.00, 7.00, 70.00);

-- CLIENTES (3 linhas)
INSERT INTO clientes (id_cliente, nome, cpf, telefone, tipo) VALUES
(1, 'Carlos Henrique Souza', '111.222.333-44', '(71) 99111-2233', 'Avulso'),
(2, 'Ana Paula Ribeiro',     '555.666.777-88', '(71) 99222-3344', 'Avulso'),
(3, 'Marcos Vinícius Lima',  '999.888.777-66', '(71) 99333-4455', 'Mensalista');

-- VEÍCULOS (3 linhas)
INSERT INTO veiculos (placa, modelo, cor, tipo_veiculo, id_cliente) VALUES
('ABC1D23', 'Onix',   'Prata',    'Carro',      1),
('DEF4G56', 'CG 160', 'Vermelha', 'Moto',       2),
('HIJ7K89', 'Hilux',  'Preta',    'Utilitário', 3);

-- VAGAS (3 linhas)
INSERT INTO vagas (numero_vaga, setor, categoria, status) VALUES
(1, 'A', 'Carro', 'Livre'),
(2, 'B', 'Moto',  'Livre'),
(3, 'A', 'Carro', 'Ocupada');

-- TÍQUETES (3 linhas): 2 finalizados em 30/10/2026 e 1 aberto em 31/10/2026
--   Carro, 200 min  -> 1ª hora 10,00 + 3 horas adicionais x 5,00 = 25,00
--   Moto,  205 min  -> 1ª hora  6,00 + 3 horas adicionais x 3,00 = 15,00
--   Utilitário mensalista, ainda no pátio (sem saída e sem valor)
INSERT INTO tiquetes (id_tiquete, placa, numero_vaga, hora_entrada, hora_saida, valor_calculado, status) VALUES
(1, 'ABC1D23', 1, '2026-10-30 08:00:00', '2026-10-30 11:20:00', 25.00, 'Finalizado'),
(2, 'DEF4G56', 2, '2026-10-30 09:15:00', '2026-10-30 12:40:00', 15.00, 'Finalizado'),
(3, 'HIJ7K89', 3, '2026-10-31 07:50:00', NULL,                 NULL,  'Aberto');
