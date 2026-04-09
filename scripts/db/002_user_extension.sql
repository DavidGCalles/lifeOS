ALTER TABLE users ADD COLUMN name VARCHAR(255) DEFAULT 'Unknown';
ALTER TABLE users ADD COLUMN description TEXT;
ALTER TABLE users ADD COLUMN profile_metadata JSONB DEFAULT '{}'::jsonb;