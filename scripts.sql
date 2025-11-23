-- Users table
CREATE TABLE IF NOT EXISTS public."User" (
    user_id   SERIAL PRIMARY KEY,
    username  TEXT NOT NULL,
    email     TEXT NOT NULL UNIQUE
);

-- Tasks table
CREATE TABLE IF NOT EXISTS public."Task" (
    task_id     SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES public."User"(user_id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT,
    is_done     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert 5 users
INSERT INTO public."User" (username, email) VALUES
  ('alice',   'alice@example.com'),
  ('bob',     'bob@example.com'),
  ('carol',   'carol@example.com'),
  ('dave',    'dave@example.com'),
  ('eve',     'eve@example.com');

  -- User 1 (alice) – 5 tasks
INSERT INTO public."Task" (user_id, title, description, is_done) VALUES
  (1, 'Task 1 for Alice', 'Alice task 5 description', TRUE);

-- User 2 (bob) – 5 tasks
INSERT INTO public."Task" (user_id, title, description, is_done) VALUES
  (2, 'Task 1 for Bob', 'Bob task 5 description', TRUE);

-- User 3 (carol) – 5 tasks
INSERT INTO public."Task" (user_id, title, description, is_done) VALUES
  (3, 'Task 1 for Carol', 'Carol task 5 description', FALSE);

-- User 4 (dave) – 5 tasks
INSERT INTO public."Task" (user_id, title, description, is_done) VALUES
  (4, 'Task 1 for Dave', 'Dave task 1 description', FALSE),
  (4, 'Task 2 for Dave', 'Dave task 5 description', FALSE);

-- User 5 (eve) – 5 tasks
INSERT INTO public."Task" (user_id, title, description, is_done) VALUES
  (5, 'Task 1 for Eve', 'Eve task 1 description', TRUE),
  (5, 'Task 2 for Eve', 'Eve task 5 description', FALSE);
