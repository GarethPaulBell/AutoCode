# orm_models.py
from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import datetime, uuid

Base = declarative_base()

# Association table for many-to-many relation between Function and Tag
function_tag_association = Table(
    'function_tag_association', Base.metadata,
    Column('function_id', String, ForeignKey('functions.function_id')),
    Column('tag_id', String, ForeignKey('tags.tag_id'))
)

class Tag(Base):
    """
    Tag for categorizing functions.
    
    Parameters:
        name (str): Unique name for the tag.
    
    Example:
        >>> tag = Tag(name="optimization")
    """
    __tablename__ = 'tags'
    tag_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    functions = relationship("Function", secondary=function_tag_association, back_populates="tags")

class Function(Base):
    """
    Represents a code module/function.
    
    Parameters:
        name (str): The name of the function.
        description (str): A brief description.
        code_snippet (str): The source code (in Julia) for the function.
    
    Example:
        >>> func = Function(name="symbolic_derivative", description="Computes the derivative", code_snippet="function symbolic_derivative(...) ... end")
    """
    __tablename__ = 'functions'
    function_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    code_snippet = Column(Text)
    creation_date = Column(DateTime, default=datetime.datetime.now)
    last_modified_date = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    unit_tests = relationship("UnitTest", back_populates="function")
    modifications = relationship("Modification", back_populates="function")
    tags = relationship("Tag", secondary=function_tag_association, back_populates="functions")

class UnitTest(Base):
    """
    Represents a unit test for a function.
    
    Parameters:
        name (str): A concise test name.
        description (str): Description of the test.
        test_case (str): The Julia test code as a string.
    
    Example:
        >>> test = UnitTest(name="test_symbolic_derivative", description="Test on polynomial", test_case="# Julia test code")
    """
    __tablename__ = 'unit_tests'
    test_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    function_id = Column(String, ForeignKey('functions.function_id'))
    name = Column(String, nullable=False)
    description = Column(Text)
    test_case = Column(Text)
    function = relationship("Function", back_populates="unit_tests")

class Modification(Base):
    """
    Represents a modification made to a function.
    
    Parameters:
        modifier (str): Who modified the code.
        description (str): Description of the modification.
    
    Example:
        >>> mod = Modification(modifier="AI", description="Fixed type error")
    """
    __tablename__ = 'modifications'
    modification_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    function_id = Column(String, ForeignKey('functions.function_id'))
    modifier = Column(String)
    modification_date = Column(DateTime, default=datetime.datetime.now)
    description = Column(Text)
    function = relationship("Function", back_populates="modifications")
