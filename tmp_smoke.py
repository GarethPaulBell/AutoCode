from src.autocode import models
import code_db

id1 = code_db.add_function('f1','f1','function f1() return 1 end')
id2 = code_db.add_function('f2','f2','function f2() return f1() end')
print('created', id1, id2)
print('add dep result:', code_db.add_dependency(id2, id1))
print('cycles before:', code_db.find_cycles())
# attempt to create cycle
print('add dep to create cycle:', code_db.add_dependency(id1, id2))
print('cycles after:', code_db.find_cycles())
print('recursion f1:', code_db.detect_recursion(id1))
print('recursion f2:', code_db.detect_recursion(id2))
# cleanup
if hasattr(code_db, '_db') and code_db._db:
	code_db._db.delete_function(id1)
	code_db._db.delete_function(id2)
print('done')
