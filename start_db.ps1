$pgCtl = "d:\H\bin\pgsql\bin\pg_ctl.exe"
$pgData = "d:\H\bin\pgsql\data"
& $pgCtl -D $pgData -l d:\H\pgsql.log start
Read-Host "PostgreSQL is running. Press Enter to stop it."
& $pgCtl -D $pgData stop
