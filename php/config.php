<?php
declare(strict_types=1);

/**
 * Conexão com o MySQL (PDO) e layout das páginas.
 * Ajuste pelas variáveis de ambiente DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
 */
function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    $dsn = getenv('AUTOPARK_DSN') ?: sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
        getenv('DB_HOST') ?: 'localhost',
        getenv('DB_PORT') ?: '3306',
        getenv('DB_NAME') ?: 'autopark'
    );
    $pdo = new PDO($dsn, getenv('DB_USER') ?: 'root', getenv('DB_PASSWORD') ?: '', [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ]);
    return $pdo;
}

/** Escapa texto para HTML (evita XSS). */
function h(?string $s): string
{
    return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8');
}

/** Abre a página. $ativa = 'clientes' ou 'veiculos' (marca o item do menu). */
function cabecalho(string $titulo, string $ativa = ''): void
{
    $itens = ['clientes' => ['clientes.php', 'Clientes'], 'veiculos' => ['veiculos.php', 'Veículos']];
    ?><!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($titulo) ?> - AutoPark</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap">
<link rel="stylesheet" href="autopark.css">
</head><body>
<header class="top"><div class="top-in">
  <a class="brand" href="clientes.php"><span class="brand-p">P</span>AutoPark</a>
  <nav class="nav" aria-label="Principal">
<?php foreach ($itens as $chave => [$href, $rotulo]): ?>
    <a href="<?= h($href) ?>"<?= $chave === $ativa ? ' aria-current="page"' : '' ?>><?= h($rotulo) ?></a>
<?php endforeach; ?>
  </nav>
</div></header>
<main class="wrap">
<?php
}

function rodape(): void
{
    echo "</main></body></html>";
}
