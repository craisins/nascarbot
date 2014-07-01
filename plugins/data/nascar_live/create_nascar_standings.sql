create table if not exists nascar_standings(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	first_name TEXT DEFAULT '',
	last_name TEXT DEFAULT '',
	driver_no INTEGER DEFAULT -1,
	rank INTEGER DEFAULT -1,
	points INTEGER DEFAULT -1
);