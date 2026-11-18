-- Local bootstrap only. Password variables come from private generated files.
IF DB_ID(N'discovery') IS NULL
    EXEC(N'CREATE DATABASE [discovery] COLLATE Latin1_General_100_CI_AS');
IF DB_ID(N'groups') IS NULL
    EXEC(N'CREATE DATABASE [groups] COLLATE Latin1_General_100_CI_AS');
GO
IF SUSER_ID(N'bassline_discovery') IS NULL
    CREATE LOGIN [bassline_discovery] WITH PASSWORD=N'$(DiscoveryPassword)', CHECK_POLICY=OFF;
IF SUSER_ID(N'bassline_groups') IS NULL
    CREATE LOGIN [bassline_groups] WITH PASSWORD=N'$(GroupsPassword)', CHECK_POLICY=OFF;
GO
USE [discovery];
GO
IF USER_ID(N'bassline_discovery') IS NULL
    CREATE USER [bassline_discovery] FOR LOGIN [bassline_discovery];
IF IS_ROLEMEMBER(N'db_datareader', N'bassline_discovery') <> 1
    ALTER ROLE [db_datareader] ADD MEMBER [bassline_discovery];
IF IS_ROLEMEMBER(N'db_datawriter', N'bassline_discovery') <> 1
    ALTER ROLE [db_datawriter] ADD MEMBER [bassline_discovery];
IF IS_ROLEMEMBER(N'db_ddladmin', N'bassline_discovery') <> 1
    ALTER ROLE [db_ddladmin] ADD MEMBER [bassline_discovery];
GO
USE [groups];
GO
IF USER_ID(N'bassline_groups') IS NULL
    CREATE USER [bassline_groups] FOR LOGIN [bassline_groups];
IF IS_ROLEMEMBER(N'db_datareader', N'bassline_groups') <> 1
    ALTER ROLE [db_datareader] ADD MEMBER [bassline_groups];
IF IS_ROLEMEMBER(N'db_datawriter', N'bassline_groups') <> 1
    ALTER ROLE [db_datawriter] ADD MEMBER [bassline_groups];
IF IS_ROLEMEMBER(N'db_ddladmin', N'bassline_groups') <> 1
    ALTER ROLE [db_ddladmin] ADD MEMBER [bassline_groups];
GO
