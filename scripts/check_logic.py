import sys, os
sys.path.insert(0, 'apps/api')
sys.path.insert(0, '.')
os.environ.update({
    'DATABASE_URL':'postgresql+asyncpg://x:x@localhost/x',
    'OPENAI_API_KEY':'sk-test', 'SUPERMEMORY_API_KEY':'sm_test',
    'SLACK_BOT_TOKEN':'xoxb-test', 'LINEAR_API_KEY':'lin_test',
    'GMAIL_CLIENT_ID':'test', 'GMAIL_CLIENT_SECRET':'test',
    'GMAIL_REFRESH_TOKEN':'test', 'SLACK_SIGNING_SECRET':'test',
})

with open('agent/orchestrator/orchestrator.py') as f:
    src = f.read()

checks = [
    ('asyncio imported',          'import asyncio' in src),
    ('AsyncGenerator in sig',     'AsyncGenerator' in src),
    ('SSE yield present',         'yield self._event' in src),
    ('OBSERVE stage emitted',     '"OBSERVE"' in src),
    ('VERIFY stage emitted',      '"VERIFY"' in src),
    ('DONE stage emitted',        '"DONE"' in src),
    ('memory.search called',      'self.memory.search' in src),
    ('policy.evaluate called',    'self.policy.evaluate' in src),
    ('executor.execute called',   'self.executor.execute' in src),
    ('verifier.verify called',    'self.verifier.verify' in src),
    ('date resolution method',    '_resolve_date' in src),
    ('injection guard used',      'self.guard.scan' in src),
]

def run_checks():
    all_ok = True
    for label, result in checks:
        status = 'OK   ' if result else 'MISS '
        if not result:
            all_ok = False
        print(f'  {status} {label}')

    with open('evaluation/runner.py') as f:
        runner = f.read()
    print()
    rcheck = 'load_scenarios' in runner and 'run_scenario' in runner
    print(f'  {"OK   " if rcheck else "MISS "} runner.py has scenario loading + run_scenario')

    with open('evaluation/seed_demo.py') as f:
        seed = f.read()
    scheck = 'golden' in seed.lower() and 'pricing_commitment' in seed
    print(f'  {"OK   " if scheck else "MISS "} seed_demo.py has golden demo chain')

    print()
    print('All logic checks passed.' if all_ok else 'Some checks FAILED — see MISS lines above.')
    return all_ok

if __name__ == '__main__':
    ok = run_checks()
    sys.exit(0 if ok else 1)

