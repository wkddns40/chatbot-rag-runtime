CREATE TABLE IF NOT EXISTS conversations (
 id uuid PRIMARY KEY, owner text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
 id bigserial PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations ON DELETE CASCADE,
 role text NOT NULL, content text NOT NULL, sources jsonb NOT NULL DEFAULT '[]',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS documents (
 id uuid PRIMARY KEY, title text NOT NULL, body text NOT NULL, acl text NOT NULL,
 approved boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS attachments (
 id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations ON DELETE CASCADE,
 title text NOT NULL, body text NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 id bigserial PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations ON DELETE CASCADE,
 owner text NOT NULL, rating integer NOT NULL CHECK (rating IN (-1,1)), created_at timestamptz DEFAULT now()
);
