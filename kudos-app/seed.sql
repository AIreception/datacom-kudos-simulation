-- Fictional demo data only. No real Datacom employee data is used.
-- INSERT OR IGNORE keeps this file idempotent when the app starts repeatedly.
INSERT OR IGNORE INTO users (name, email, department, role) VALUES
    ('Alice Ng',       'alice.ng@example.internal',       'Engineering',       'employee'),
    ('Ben Okafor',     'ben.okafor@example.internal',     'Product',           'employee'),
    ('Carla Mendes',   'carla.mendes@example.internal',   'Design',            'employee'),
    ('Daniel Kim',     'daniel.kim@example.internal',     'Engineering',       'employee'),
    ('Elif Yilmaz',    'elif.yilmaz@example.internal',    'People & Culture',  'employee'),
    ('Farhan Ali',     'farhan.ali@example.internal',     'Finance',           'employee'),
    ('Grace Chen',     'grace.chen@example.internal',     'Customer Success',  'employee'),
    ('Hemi Walker',    'hemi.walker@example.internal',    'Security',          'employee'),
    ('Morgan Reed',    'morgan.reed@example.internal',    'People & Culture',  'admin');
