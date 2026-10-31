# AutoPark — Sistema de Gerenciamento de Estacionamento

Projeto de Banco de Dados (MySQL) para automatizar tíquetes, vagas e mensalistas do AutoPark, um estacionamento comercial em zona urbana central que hoje controla tudo em fichas de papel.

- **Integrantes:** Diego de A. C. Moreira e Yago de A. C. Santiago
- **Disciplina:** Banco de Dados
- **Professor:** Gean Paulo

## Sumário

1. [O problema e a solução](#1-o-problema-e-a-solução)
2. [O que há no projeto](#2-o-que-há-no-projeto)
3. [Requisitos](#3-requisitos)
4. [Passo a passo para rodar](#4-passo-a-passo-para-rodar)
5. [Modelo de dados](#5-modelo-de-dados)
6. [Regras de cobrança](#6-regras-de-cobrança)
7. [As aplicações](#7-as-aplicações)
8. [Consultas SQL](#8-consultas-sql)
9. [Testes realizados](#9-testes-realizados)
10. [Problemas comuns](#10-problemas-comuns)
11. [Limitações e próximos passos](#11-limitações-e-próximos-passos)

## 1. O problema e a solução

**Problemas do processo atual:** filas nos horários de pico, erros no cálculo da permanência e perda de controle sobre as vagas livres.

**Problema principal:** incerteza na ocupação das vagas e lentidão no faturamento por hora.

**Solução proposta:** um banco de dados que automatiza tíquetes, vagas e mensalistas.

**Impacto esperado:** agilidade na recepção e precisão no controle financeiro do caixa.

## 2. O que há no projeto

```
autopark/
├── autopark_mysql.sql        Arquivo único da base: cria banco, tabelas e carrega os dados
├── sql/
│   ├── 01_modelo_fisico.sql  Modelo físico: banco, tabelas, chaves e restrições
│   ├── 02_dados.sql          Carga de dados: 3 linhas por tabela
│   └── 03_consultas.sql      As 10 consultas
├── docs/
│   ├── modelo_conceitual.png Diagrama do modelo conceitual
│   ├── modelo_logico.png     Diagrama do modelo lógico
│   ├── modelos.md            Descrição dos modelos e do que mudou
│   └── consultas_resultados.md  Enunciado, código e resultado de cada consulta
├── php/                      Aplicação de cadastro (PHP + PDO)
│   ├── config.php            Conexão com o MySQL e layout
│   ├── clientes.php          Cadastro de clientes
│   ├── veiculos.php          Cadastro de veículos
│   └── index.php
├── app.py                    Sistema completo do estacionamento (Flask)
├── requirements.txt          Dependências do Python
└── docker-compose.yml        MySQL 8 para desenvolvimento (opcional)
```

Além dos arquivos, há uma apresentação de slides e um relatório detalhado do projeto.

## 3. Requisitos

| Para usar | Precisa de |
| --- | --- |
| A base de dados | MySQL 5.7 ou 8.x (escrita para essas versões, ainda não executada em MySQL real; veja a seção 9) |
| A aplicação PHP | PHP 8 ou superior com a extensão `pdo_mysql` |
| O sistema Flask | Python 3.9 ou superior (`flask`, `pymysql`, `cryptography`) |

## 4. Passo a passo para rodar

### 4.1 Criar a base de dados

Com o MySQL ligado, na pasta do projeto:

```
mysql -u root -p < autopark_mysql.sql
```

O arquivo **recria o banco `autopark` do zero** (`DROP DATABASE IF EXISTS autopark`). Se já houver dados seus nele, faça backup antes.

Para executar por etapas, rode nesta ordem: `sql/01_modelo_fisico.sql`, `sql/02_dados.sql` e `sql/03_consultas.sql`.

Sem MySQL instalado, há uma alternativa com Docker:

```
docker compose up -d
```

Isso sobe um MySQL 8 na porta 3306 com senha de `root` igual a `autopark`.

### 4.2 Configurar a conexão

As duas aplicações leem as mesmas variáveis de ambiente. Os valores padrão são `localhost`, `3306`, `autopark`, `root` e senha vazia.

| Variável | Significado | Padrão |
| --- | --- | --- |
| `DB_HOST` | Servidor do MySQL | `localhost` |
| `DB_PORT` | Porta | `3306` |
| `DB_NAME` | Nome do banco | `autopark` |
| `DB_USER` | Usuário | `root` |
| `DB_PASSWORD` | Senha | vazia |

No **PowerShell (Windows)**:

```
$env:DB_PASSWORD="sua_senha"
```

No **Linux ou macOS**:

```
export DB_PASSWORD=sua_senha
```

A variável vale apenas para a janela de terminal em uso.

### 4.3 Rodar a aplicação PHP de cadastro

```
cd php
php -S localhost:8080
```

Abra http://localhost:8080 para cadastrar clientes e http://localhost:8080/veiculos.php para cadastrar veículos. No XAMPP ou WAMP, copie a pasta `php` para `htdocs` e acesse pelo navegador.

### 4.4 Rodar o sistema completo (Flask)

```
py -m pip install -r requirements.txt
py app.py
```

(No Linux ou macOS, use `python3` no lugar de `py`.)

Abra http://localhost:5000. Na primeira execução o sistema confere as tabelas, carrega as tarifas e cria 26 vagas (setores A, B e C) se as tabelas estiverem vazias.

## 5. Modelo de dados

Cinco tabelas e quatro relacionamentos 1:N:

- um cliente possui vários veículos (`clientes` 1:N `veiculos`);
- um veículo gera vários tíquetes (`veiculos` 1:N `tiquetes`);
- uma vaga aparece em vários tíquetes ao longo do tempo (`vagas` 1:N `tiquetes`);
- uma tarifa vale para vários veículos do mesmo tipo (`tarifas` 1:N `veiculos`).

| Tabela | Chave primária | Chaves estrangeiras | Conteúdo |
| --- | --- | --- | --- |
| `clientes` (R1) | `id_cliente` | — | nome, cpf (único), telefone, tipo (Mensalista ou Avulso) |
| `veiculos` (R2) | `placa` | `tipo_veiculo` → tarifas; `id_cliente` → clientes | modelo, cor |
| `vagas` (R3) | `numero_vaga` | — | setor, categoria (Carro, Moto ou PCD), status (Livre ou Ocupada) |
| `tiquetes` (R4) | `id_tiquete` | `placa` → veiculos; `numero_vaga` → vagas | hora_entrada, hora_saida, valor_calculado, status (Aberto ou Finalizado) |
| `tarifas` | `tipo_veiculo` | — | tolerância e valores de cobrança |

**Integridade garantida pelo banco:** um veículo e uma vaga só podem ter um tíquete **aberto** por vez. O MySQL não tem índice único parcial, então duas colunas geradas (`placa_aberta` e `vaga_aberta`) só recebem valor enquanto o tíquete está Aberto, e um índice UNIQUE sobre elas recusa duplicidades. Há também uma restrição que impede a saída de ser anterior à entrada.

Os diagramas estão em `docs/modelo_conceitual.png` e `docs/modelo_logico.png`. Os arquivos da I unidade não estavam disponíveis; os modelos foram reconstruídos a partir dos requisitos R1 a R4.

## 6. Regras de cobrança

Ficam na tabela `tarifas`, por tipo de veículo. **Os valores abaixo são uma suposição do projeto**, já que a especificação não os traz; confirme com o AutoPark.

| Tipo | Tolerância | 1ª hora | Hora adicional | Teto por 24 h |
| --- | --- | --- | --- | --- |
| Carro | 10 min | R$ 10,00 | R$ 5,00 | R$ 50,00 |
| Moto | 10 min | R$ 6,00 | R$ 3,00 | R$ 30,00 |
| Utilitário | 10 min | R$ 14,00 | R$ 7,00 | R$ 70,00 |

- Hora iniciada conta como hora cheia.
- Saída dentro da tolerância não paga.
- Cada 24 horas completas cobram o teto; o restante é calculado pela tabela, limitado ao mesmo teto.
- Mensalista não paga por permanência.

Para alterar um valor:

```sql
UPDATE tarifas SET valor_primeira_hora = 12.00 WHERE tipo_veiculo = 'Carro';
```

## 7. As aplicações

### Cadastro em PHP (`php/`)

Formulários para cadastrar clientes e veículos, com a lista dos registros gravados. Usa PDO com comandos preparados (contra injeção de SQL), valida CPF, placa e tipo, trata CPF ou placa repetidos com mensagem clara e escapa todo texto exibido (contra XSS).

### Sistema completo (`app.py`, Flask)

| Tela | Função |
| --- | --- |
| Painel | Mapa do pátio com vagas livres e ocupadas, tempo de cada veículo e faturamento do dia |
| Entrada | Reconhece a placa (inclusive de mensalistas), escolhe a primeira vaga livre da categoria certa e gera o tíquete para imprimir |
| Saída | Calcula permanência e valor, recebe e libera a vaga |
| Clientes, Veículos, Vagas | Cadastros de R1 a R3 |
| Caixa | Fechamento por dia, com cada saída e o total arrecadado |

Entrada e saída rodam em transação, e a escolha da vaga usa `SELECT ... FOR UPDATE` para dois atendentes não receberem a mesma vaga.

## 8. Consultas SQL

As 10 consultas estão em `sql/03_consultas.sql`. O enunciado, o código e o resultado de cada uma estão em `docs/consultas_resultados.md`.

| Nº | Recurso | Pergunta |
| --- | --- | --- |
| 1 | COUNT + GROUP BY | Quantos clientes de cada tipo? |
| 2 | COUNT, SUM, AVG, MIN, MAX | Resumo financeiro dos tíquetes finalizados |
| 3 | LEFT JOIN | Situação atual de cada vaga e a placa que a ocupa |
| 4 | LIKE | Clientes com "Souza" no nome |
| 5 | JOIN + LIKE | Veículos com modelo iniciado por H ou O e seus donos |
| 6 | BETWEEN (valores) | Tíquetes entre R$ 10 e R$ 20 |
| 7 | JOIN de 3 tabelas + BETWEEN (datas) | Tíquetes com entrada em 30/10/2026 |
| 8 | GROUP BY + HAVING | Categorias com 2 ou mais vagas |
| 9 | JOIN + GROUP BY + SUM | Faturamento por tipo de veículo |
| 10 | JOIN de 3 tabelas + GROUP BY + HAVING | Clientes que pagaram mais de R$ 20 |

## 9. Testes realizados

| Teste | Resultado |
| --- | --- |
| Cálculo de tarifa, 12 casos | 12 de 12 corretos |
| Renderização das 9 telas do Flask | 9 de 9 corretas |
| 26 verificações das rotas do Flask (entrada, saída, caixa, cadastros) | 26 de 26 corretas |
| Cadastro em PHP (válido, CPF repetido, CPF inválido, placa repetida, texto com script) | comportamento esperado |
| 10 consultas SQL sobre a base de 3 linhas por tabela | 10 de 10 executadas |

**Importante:** esses testes rodaram com **SQLite no lugar do MySQL**, porque o ambiente de desenvolvimento não tinha um servidor MySQL. O SQLite não exercita recursos do MySQL usados aqui: colunas geradas `STORED`, `CHECK`, `ENUM`, `SELECT ... FOR UPDATE` e `TIMESTAMPDIFF`. O teste definitivo é rodar `autopark_mysql.sql` e as consultas no seu MySQL e comparar com `docs/consultas_resultados.md`. Se algum comando falhar na sua versão do MySQL, ajuste o script e registre a diferença.

## 10. Problemas comuns

| Mensagem | Causa e solução |
| --- | --- |
| `ModuleNotFoundError: No module named 'pymysql'` | Faltou instalar as dependências. Rode `py -m pip install -r requirements.txt`. |
| `Access denied for user 'root'@'localhost' (using password: NO)` | O `root` tem senha e o app tentou sem ela. Defina `DB_PASSWORD` (seção 4.2). |
| `Can't connect to MySQL server` | O MySQL não está ligado ou a porta/host estão errados. Confira `DB_HOST` e `DB_PORT`. |
| `Unknown database 'autopark'` | A base ainda não foi criada. Rode `autopark_mysql.sql` (seção 4.1). |
| `could not find driver` (PHP) | Falta a extensão `pdo_mysql`. Ative-a no `php.ini`. |

## 11. Limitações e próximos passos

- As tarifas são valores supostos e precisam ser confirmadas.
- O mensalista só é isento da cobrança por hora; ainda não há mensalidade com vencimento e cobrança.
- Não há login nem perfis de acesso, e o caixa não registra a forma de pagamento.
- Os cadastros permitem incluir registros, mas ainda não editar nem excluir.
- A execução em MySQL real ainda precisa ser confirmada (seção 9).

Próximos passos sugeridos: tabela de mensalidades, login com perfis, forma de pagamento e fechamento por turno, edição e exclusão de cadastros, e leitura automática de placa por câmera.
