#!/usr/bin/env python3
# -*- coding utf-8 -*-

import asyncio, logging

import aiomysql


def log(sql, args=()):
	logging.info('SQL: %s' % sql)

async def create_pool(loop, **kw):
	logging.info('creating database connection pool...')
	global __pool
	__pool = await aiomysql.create_pool(
		host=kw.get('host', 'localhost'),
		port=kw.get('port', 3306),
		user=kw['user'],
		password=kw['password'],
		db=kw['db'],
		charset=kw.get('charset', 'utf8'),
		autocommit=kw.get('autocommit', True),
		maxsize=kw.get('maxsize', 10),
		minsize=kw.get('minsize', 1),
		loop=loop
		)

# 执行select语句
async def select(sql, args, size=None):
	log(sql, args)
	global __pool
	with await __pool as conn:
		cur = await conn.cursor(aiomysql.DictCursor)
		await cur.execute(sql.replace('?', '%s'), args or ())
		if size:
			rs = await cur.fetchmany(size)
		else:
			rs = await cur.fetchall()
		await cur.close()
		logging.info('row returned: %s' % len(rs))
		return rs

# 执行insert、update、delete语句
async def execute(sql, args):
	log(sql)
	with await __pool as conn:
		try:
			cur = await conn.cursor()
			await cur.execute(sql.replace('?', '%s'), args)
			affected = cur.rawcount()
			await cur.close()
		except BaseException as e:
			raise
		return affected


class Field(object):

	def __init__(self, name, column_type, primary_key, default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		return '<%s, %s:%S>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):

	def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
		super().__init__(name, ddl, primary_key, default)

class IntegerField(Field):

	def __init__(self, name=None, primary_key=False, default=0):
		pass

class FloatField(Field):

	def __init__(self, name=None, primary_key=False, default=0.0):
		pass

class BooleanField(Field):

	def __init__(self, name=None, default=False):
		pass

class TextleanField(Field):

	def __init__(self, name=None, default=None):
		pass



class ModelMetaclass(type):

	def __new__(cls, name, bases, attrs):
		pass

# ORM映射 基类
class Model(dict, metaclass=ModelMetaclass):

	def __init__(self, **kw):
		super(Model, self).__init__(**kw)

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if value is None:
			field = slef.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.info('using default value for %s: %s' % (key, str(value)))
				setattr(self, key, value)
		return value
	
	@classmethod
	async def find(cls, pk):
		' find object by primary key'
		rs = await select("%s where '%s'=?" % (cls.__select__, cls.__primary_key__), [pk], 1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	async def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = await execute(self.__insert__, args)
		if row != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)