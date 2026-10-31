<?php
declare(strict_types=1);

/**
 * Conexão com o MySQL (PDO) e funções auxiliares de layout.
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

function cabecalho(string $titulo): void
{
    ?><!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= h($titulo) ?> - AutoPark</title>
<style>
 body{margin:0;font-family:system-ui,sans-serif;background:#f4f6f8;color:#1c2530}
 nav{background:#101a2b;padding:0 16px}nav b{color:#fff;margin-right:16px;display:inline-block;padding:14px 0}
 nav a{color:#c9d3e3;text-decoration:none;padding:14px 12px;display:inline-block}nav a:hover{background:#1b2a45}
 main{max-width:1000px;margin:20px auto;padding:0 16px}
 .card{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:16px;margin-bottom:16px}
 h1{font-size:1.3rem;margin:0 0 12px}
 form{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;align-items:end}
 label{display:flex;flex-direction:column;font-size:.8rem;color:#6b7785;gap:4px}
 input,select{padding:9px;border:1px solid #dde3ea;border-radius:6px;font-size:1rem}
 button{background:#0b5fff;color:#fff;border:0;padding:10px 16px;border-radius:6px;font-size:1rem;cursor:pointer}
 table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #dde3ea;font-size:.92rem}
 th{color:#6b7785}.ok{background:#dff5ec;color:#12805c;padding:10px 14px;border-radius:6px;margin-bottom:12px}
 .erro{background:#fde7e7;color:#c62828;padding:10px 14px;border-radius:6px;margin-bottom:12px}
</style></head><body>
<nav><b>🅿 AutoPark</b><a href="clientes.php">Clientes</a><a href="veiculos.php">Veículos</a></nav>
<main>
<?php
}

function rodape(): void
{
    echo "</main></body></html>";
}
