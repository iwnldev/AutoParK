<?php
declare(strict_types=1);
require __DIR__ . '/config.php';

$erros = [];
$ok = isset($_GET['ok']);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $nome     = trim((string) ($_POST['nome'] ?? ''));
    $cpf      = trim((string) ($_POST['cpf'] ?? ''));
    $telefone = trim((string) ($_POST['telefone'] ?? ''));
    $tipo     = (string) ($_POST['tipo'] ?? '');

    if ($nome === '' || mb_strlen($nome) > 120) {
        $erros[] = 'Informe o nome (até 120 caracteres).';
    }
    if (!in_array($tipo, ['Mensalista', 'Avulso'], true)) {
        $erros[] = 'Tipo inválido.';
    }
    if ($cpf !== '' && !preg_match('/^\d{3}\.\d{3}\.\d{3}-\d{2}$/', $cpf)) {
        $erros[] = 'CPF deve estar no formato 000.000.000-00.';
    }
    if ($tipo === 'Mensalista' && $cpf === '') {
        $erros[] = 'CPF é obrigatório para mensalista.';
    }
    if (mb_strlen($telefone) > 20) {
        $erros[] = 'Telefone muito longo.';
    }

    if (!$erros) {
        try {
            $st = db()->prepare(
                'INSERT INTO clientes (nome, cpf, telefone, tipo) VALUES (:nome, :cpf, :telefone, :tipo)'
            );
            $st->execute([
                ':nome'     => $nome,
                ':cpf'      => $cpf !== '' ? $cpf : null,
                ':telefone' => $telefone !== '' ? $telefone : null,
                ':tipo'     => $tipo,
            ]);
            header('Location: clientes.php?ok=1');
            exit;
        } catch (PDOException $e) {
            // SQLSTATE 23000 = violação de integridade (CPF repetido)
            $erros[] = $e->getCode() === '23000'
                ? 'Já existe um cliente com este CPF.'
                : 'Erro ao gravar no banco de dados.';
        }
    }
}

$lista = db()->query('SELECT id_cliente, nome, cpf, telefone, tipo FROM clientes ORDER BY id_cliente DESC')->fetchAll();

cabecalho('Clientes');
?>
<div class="card">
  <h1>Cadastro de cliente</h1>
  <?php if ($ok): ?><div class="ok">Cliente cadastrado com sucesso.</div><?php endif; ?>
  <?php foreach ($erros as $e): ?><div class="erro"><?= h($e) ?></div><?php endforeach; ?>
  <form method="post" autocomplete="off">
    <label>Nome<input name="nome" required maxlength="120" value="<?= h($_POST['nome'] ?? '') ?>"></label>
    <label>CPF<input name="cpf" maxlength="14" placeholder="000.000.000-00" value="<?= h($_POST['cpf'] ?? '') ?>"></label>
    <label>Telefone<input name="telefone" maxlength="20" value="<?= h($_POST['telefone'] ?? '') ?>"></label>
    <label>Tipo
      <select name="tipo">
        <?php foreach (['Avulso', 'Mensalista'] as $t): ?>
          <option <?= (($_POST['tipo'] ?? 'Avulso') === $t) ? 'selected' : '' ?>><?= h($t) ?></option>
        <?php endforeach; ?>
      </select>
    </label>
    <button type="submit">Cadastrar</button>
  </form>
</div>
<div class="card">
  <h1>Clientes cadastrados (<?= count($lista) ?>)</h1>
  <table>
    <tr><th>ID</th><th>Nome</th><th>CPF</th><th>Telefone</th><th>Tipo</th></tr>
    <?php foreach ($lista as $c): ?>
      <tr><td><?= (int) $c['id_cliente'] ?></td><td><?= h($c['nome']) ?></td><td><?= h($c['cpf']) ?></td>
          <td><?= h($c['telefone']) ?></td><td><?= h($c['tipo']) ?></td></tr>
    <?php endforeach; ?>
  </table>
</div>
<?php rodape();
