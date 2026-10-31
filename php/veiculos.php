<?php
declare(strict_types=1);
require __DIR__ . '/config.php';

$erros = [];
$ok = isset($_GET['ok']);
$tipos = ['Carro', 'Moto', 'Utilitário'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $placa   = strtoupper(preg_replace('/[^A-Za-z0-9]/', '', (string) ($_POST['placa'] ?? '')));
    $modelo  = trim((string) ($_POST['modelo'] ?? ''));
    $cor     = trim((string) ($_POST['cor'] ?? ''));
    $tipo    = (string) ($_POST['tipo_veiculo'] ?? '');
    $cliente = filter_var($_POST['id_cliente'] ?? '', FILTER_VALIDATE_INT);

    if (!preg_match('/^[A-Z0-9]{6,10}$/', $placa)) {
        $erros[] = 'Placa inválida (use de 6 a 10 letras/números).';
    }
    if (!in_array($tipo, $tipos, true)) {
        $erros[] = 'Tipo de veículo inválido.';
    }
    if ($cliente === false) {
        $erros[] = 'Selecione o proprietário.';
    }
    if (mb_strlen($modelo) > 60 || mb_strlen($cor) > 30) {
        $erros[] = 'Modelo (máx. 60) ou cor (máx. 30) muito longos.';
    }

    if (!$erros) {
        try {
            $st = db()->prepare(
                'INSERT INTO veiculos (placa, modelo, cor, tipo_veiculo, id_cliente)
                 VALUES (:placa, :modelo, :cor, :tipo, :cliente)'
            );
            $st->execute([
                ':placa'   => $placa,
                ':modelo'  => $modelo !== '' ? $modelo : null,
                ':cor'     => $cor !== '' ? $cor : null,
                ':tipo'    => $tipo,
                ':cliente' => $cliente,
            ]);
            header('Location: veiculos.php?ok=1');
            exit;
        } catch (PDOException $e) {
            $erros[] = $e->getCode() === '23000'
                ? 'Placa já cadastrada ou proprietário inexistente.'
                : 'Erro ao gravar no banco de dados.';
        }
    }
}

$clientes = db()->query('SELECT id_cliente, nome, tipo FROM clientes ORDER BY nome')->fetchAll();
$lista = db()->query(
    'SELECT v.placa, v.modelo, v.cor, v.tipo_veiculo, c.nome
     FROM veiculos v JOIN clientes c ON c.id_cliente = v.id_cliente ORDER BY v.placa'
)->fetchAll();

cabecalho('Veículos');
?>
<div class="card">
  <h1>Cadastro de veículo</h1>
  <?php if ($ok): ?><div class="ok">Veículo cadastrado com sucesso.</div><?php endif; ?>
  <?php foreach ($erros as $e): ?><div class="erro"><?= h($e) ?></div><?php endforeach; ?>
  <form method="post" autocomplete="off">
    <label>Placa<input name="placa" required maxlength="10" style="text-transform:uppercase" value="<?= h($_POST['placa'] ?? '') ?>"></label>
    <label>Modelo<input name="modelo" maxlength="60" value="<?= h($_POST['modelo'] ?? '') ?>"></label>
    <label>Cor<input name="cor" maxlength="30" value="<?= h($_POST['cor'] ?? '') ?>"></label>
    <label>Tipo
      <select name="tipo_veiculo">
        <?php foreach ($tipos as $t): ?><option><?= h($t) ?></option><?php endforeach; ?>
      </select>
    </label>
    <label>Proprietário
      <select name="id_cliente" required>
        <?php foreach ($clientes as $c): ?>
          <option value="<?= (int) $c['id_cliente'] ?>"><?= h($c['nome']) ?> (<?= h($c['tipo']) ?>)</option>
        <?php endforeach; ?>
      </select>
    </label>
    <button type="submit">Cadastrar</button>
  </form>
</div>
<div class="card">
  <h1>Frota cadastrada (<?= count($lista) ?>)</h1>
  <table>
    <tr><th>Placa</th><th>Modelo</th><th>Cor</th><th>Tipo</th><th>Proprietário</th></tr>
    <?php foreach ($lista as $v): ?>
      <tr><td><b><?= h($v['placa']) ?></b></td><td><?= h($v['modelo']) ?></td><td><?= h($v['cor']) ?></td>
          <td><?= h($v['tipo_veiculo']) ?></td><td><?= h($v['nome']) ?></td></tr>
    <?php endforeach; ?>
  </table>
</div>
<?php rodape();
