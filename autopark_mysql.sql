-- ============================================================================
-- AutoPark - ARQUIVO DA BASE DE DADOS (MySQL 5.7+ / 8.x)
-- Cria o banco, as tabelas (modelo físico) e carrega 3 linhas por tabela.
-- Uso:  mysql -u root -p < autopark_mysql.sql
-- ATENÇÃO: recria o banco "autopark" do zero (DROP DATABASE IF EXISTS).
-- ============================================================================
DROP DATABASE IF EXISTS autopark;

-- ============================================================================
-- AutoPark - Sistema de Gerenciamento de Estacionamento
-- MODELO FÍSICO (linguagem SQL) - MySQL 5.7+ / 8.x - InnoDB
--
-- Relacionamentos do modelo lógico:
--   TARIFAS  (1) --- (N) VEÍCULOS (1) --- (N) TÍQUETES (N) --- (1) VAGAS
--   CLIENTES (1) --- (N) VEÍCULOS
-- ============================================================================

CREATE DATABASE IF NOT EXISTS autopark
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE autopark;

-- ----------------------------------------------------------------------------
-- TARIFAS: parâmetros de cobrança por tipo de veículo (editáveis sem mexer no código)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tarifas (
    tipo_veiculo          ENUM('Carro','Moto','Utilitário') NOT NULL,
    tolerancia_min        INT           NOT NULL DEFAULT 10,
    valor_primeira_hora   DECIMAL(10,2) NOT NULL,
    valor_hora_adicional  DECIMAL(10,2) NOT NULL,
    valor_diaria_max      DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (tipo_veiculo)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- R1 - CLIENTES: cadastro de proprietários
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente  INT AUTO_INCREMENT,
    nome        VARCHAR(120) NOT NULL,
    cpf         VARCHAR(14)  NULL,
    telefone    VARCHAR(20)  NULL,
    tipo        ENUM('Mensalista','Avulso') NOT NULL DEFAULT 'Avulso',
    PRIMARY KEY (id_cliente),
    UNIQUE KEY ux_clientes_cpf (cpf)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- R2 - VEÍCULOS: controle de frota (a placa é o identificador)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS veiculos (
    placa         VARCHAR(10) NOT NULL,
    modelo        VARCHAR(60) NULL,
    cor           VARCHAR(30) NULL,
    tipo_veiculo  ENUM('Carro','Moto','Utilitário') NOT NULL DEFAULT 'Carro',
    id_cliente    INT NOT NULL,
    PRIMARY KEY (placa),
    CONSTRAINT fk_veiculo_cliente FOREIGN KEY (id_cliente)
        REFERENCES clientes (id_cliente),
    CONSTRAINT fk_veiculo_tarifa FOREIGN KEY (tipo_veiculo)
        REFERENCES tarifas (tipo_veiculo)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- R3 - VAGAS: mapeamento do pátio
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vagas (
    numero_vaga  INT         NOT NULL,
    setor        VARCHAR(20) NOT NULL,
    categoria    ENUM('Carro','Moto','PCD') NOT NULL DEFAULT 'Carro',
    status       ENUM('Livre','Ocupada')    NOT NULL DEFAULT 'Livre',
    PRIMARY KEY (numero_vaga)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- R4 - TÍQUETES: registro de permanência
-- As colunas geradas placa_aberta e vaga_aberta só têm valor enquanto o tíquete
-- está Aberto. Com o índice UNIQUE o próprio banco impede dois tíquetes abertos
-- para a mesma placa ou a mesma vaga (valores NULL não colidem).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tiquetes (
    id_tiquete       INT AUTO_INCREMENT,
    placa            VARCHAR(10)   NOT NULL,
    numero_vaga      INT           NOT NULL,
    hora_entrada     DATETIME      NOT NULL,
    hora_saida       DATETIME      NULL,
    valor_calculado  DECIMAL(10,2) NULL,
    status           ENUM('Aberto','Finalizado') NOT NULL DEFAULT 'Aberto',
    placa_aberta     VARCHAR(10)
        GENERATED ALWAYS AS (IF(status = 'Aberto', placa, NULL)) STORED,
    vaga_aberta      INT
        GENERATED ALWAYS AS (IF(status = 'Aberto', numero_vaga, NULL)) STORED,
    PRIMARY KEY (id_tiquete),
    CONSTRAINT fk_tiquete_veiculo FOREIGN KEY (placa)
        REFERENCES veiculos (placa),
    CONSTRAINT fk_tiquete_vaga FOREIGN KEY (numero_vaga)
        REFERENCES vagas (numero_vaga),
    CONSTRAINT ck_tiquete_periodo
        CHECK (hora_saida IS NULL OR hora_saida >= hora_entrada),
    UNIQUE KEY ux_tiquete_aberto_placa (placa_aberta),
    UNIQUE KEY ux_tiquete_aberto_vaga (vaga_aberta),
    KEY ix_tiquete_entrada (hora_entrada),
    KEY ix_tiquete_saida (hora_saida)
) ENGINE=InnoDB;

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
