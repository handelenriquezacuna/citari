-- 01-create-database.sql
-- Proyecto: Citari
-- Contenido: crea la base de datos citari desde cero.
-- Los identificadores del esquema estan en espanol (ASCII puro).

USE master;
GO

IF EXISTS (SELECT name FROM sys.databases WHERE name = N'citari')
BEGIN
    ALTER DATABASE citari SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE citari;
END

CREATE DATABASE citari
COLLATE Latin1_General_CI_AI;
GO

USE citari;
GO

PRINT '[01-create-database] base de datos citari creada ... OK';
GO
