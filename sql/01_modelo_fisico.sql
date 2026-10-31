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
