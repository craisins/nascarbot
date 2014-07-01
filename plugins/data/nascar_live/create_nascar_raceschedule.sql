create table if not exists nascar_raceschedule(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	timestamp REAL DEFAULT 0,
	name TEXT DEFAULT '',
	speedway DEFAULT '',
	network DEFAULT ''
);