import code_db
fid = 'f73c3823-939a-46eb-bd75-6fba85c6b4a6'
updated = False
for t in code_db._db.functions[fid].unit_tests:
    if t.test_id == 'c84cb7f3-f7ea-43a5-8e71-64039290f665':
        t.test_case = '''using Test

@testset "smoke_fib" begin
    @test fibonacci(0) == 0
    @test fibonacci(1) == 1
    @test fibonacci(5) == 5
end
'''
        updated = True
        print('Updated test', t.test_id)
        break
if updated:
    code_db.save_db()
    print('Saved DB')
else:
    print('Test ID not found')
for t in code_db._db.functions[fid].unit_tests:
    print('---')
    print('TEST_ID:', t.test_id)
    print('TEST_NAME:', t.name)
    print('TEST_CODE:\n', t.test_case)
