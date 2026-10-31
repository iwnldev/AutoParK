# AutoPark — Modelos conceitual, lógico e físico

## Modelo conceitual (`modelo_conceitual.png`)

Entidades: **CLIENTE**, **VEÍCULO**, **VAGA**, **TÍQUETE** (requisitos R1 a R4) e **TARIFA**.

| Relacionamento | Cardinalidade | Significado |
|---|---|---|
| CLIENTE possui VEÍCULO | 1 : N | um proprietário pode ter vários veículos |
| VEÍCULO gera TÍQUETE | 1 : N | cada passagem pelo estacionamento gera um tíquete |
| VAGA é registrada em TÍQUETE | 1 : N | uma vaga é usada por vários tíquetes ao longo do tempo |
| TARIFA enquadra VEÍCULO | 1 : N | a cobrança depende do tipo do veículo |

## Modelo lógico (`modelo_logico.png`)

```
clientes (PK id_cliente, nome, cpf [UK], telefone, tipo)
tarifas  (PK tipo_veiculo, tolerancia_min, valor_primeira_hora, valor_hora_adicional, valor_diaria_max)
veiculos (PK placa, modelo, cor, FK tipo_veiculo -> tarifas, FK id_cliente -> clientes)
vagas    (PK numero_vaga, setor, categoria, status)
tiquetes (PK id_tiquete, FK placa -> veiculos, FK numero_vaga -> vagas,
          hora_entrada, hora_saida, valor_calculado, status)
```

Normalização: todas as tabelas estão na 3FN (sem dependências parciais ou transitivas;
a tarifa fica em tabela própria para não repetir valores em cada veículo).

## O que foi atualizado em relação ao modelo inicial (R1 a R4)

1. **Nova entidade TARIFA**: os valores de cobrança saem do código e passam a ser dados, por tipo de veículo.
2. **VEÍCULO.tipo_veiculo** vira chave estrangeira para TARIFA.
3. **CLIENTE.cpf** é único e opcional (clientes avulsos podem não informar).
4. **TÍQUETE.status** (Aberto / Finalizado) e duas colunas geradas com índice único garantem, no próprio banco,
   que um veículo ou uma vaga só tenha um tíquete aberto por vez.
5. **Restrição de período**: a saída nunca pode ser anterior à entrada.
6. Campos de domínio fixo (tipo, categoria, status) usam `ENUM`.

> Observação: os arquivos originais da I unidade não estavam disponíveis; os modelos foram reconstruídos a partir da
> especificação R1–R4. Se houver diferenças em relação ao material entregue, basta ajustar os nomes.

## Modelo físico

`sql/01_modelo_fisico.sql` (MySQL 5.7+/8.x, InnoDB, utf8mb4).
