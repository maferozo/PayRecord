-- ===========================================================
-- PAYRECORD — Creación de la base de datos y del usuario
-- Ejecutar UNA SOLA VEZ con un usuario administrador de MySQL
-- (por ejemplo root), desde MySQL Workbench o la consola.
--
-- Antes de ejecutar: reemplazar __CONTRASENA__ por la misma
-- contraseña que figura en DB_PASSWORD del archivo .env
-- ===========================================================

-- utf8mb4 para admitir tildes, ñ y emojis sin corrupción.
CREATE DATABASE IF NOT EXISTS payrecord
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Usuario dedicado. No se usa root desde la aplicación (§28).
CREATE USER IF NOT EXISTS 'payrecord'@'localhost'
    IDENTIFIED BY '__CONTRASENA__';

-- Permisos acotados a la base de la aplicación.
-- Se incluye CREATE/DROP porque Django los necesita para las migraciones
-- y para crear la base de datos de pruebas (test_payrecord).
GRANT ALL PRIVILEGES ON payrecord.* TO 'payrecord'@'localhost';
GRANT ALL PRIVILEGES ON `test\_payrecord`.* TO 'payrecord'@'localhost';

FLUSH PRIVILEGES;

-- Verificación
SELECT SCHEMA_NAME AS base_creada
FROM INFORMATION_SCHEMA.SCHEMATA
WHERE SCHEMA_NAME = 'payrecord';
