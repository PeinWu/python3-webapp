#!/usr/bin/env python3
# -*-coding:utf-8-*-

__author__='WuYe'

import  asyncio,logging

import  aiomysql

def log(sql,arg=()):
    logging.info('SQL: %s'%sql)

# Create the connecting pool,evet http request go through pool to database
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','localhost')
        port = kw.get('port',3306)
        user = kw['user']
        password = kw['password']
        db = kw['db']
        charset = kw.get['chartset','utf-8']
        autocommit = kw.get('autocommit',True)
        maxsize = kw.get('autocommit',10)
        minsize = kw.get('autocommit',1)
    )

# Destory the connecting pool
async def destory_pool():
    global __pool
    if __pool is not None:
        __pool.close()
        await __pool.wait_closed()


# select method
async def select(sql,args,size=None):

    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?','%'),args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()

        logging.info('rows returned: %s'%len(rs))
        return rs
#insert ,update,delete method
async def execute(sql,args,autocommit=True):

        async with __pool.get() as conn:
            if not autocommit:
                await conn.begin()
            try:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql.replace('?','%s'),args or ())

                    affected = cur.rowcount
                if not autocommit:
                    await conn.commit()
            except BaseException as e:
                if not autocommit:
                    await  conn.rollback()
                raise
            return affected

def create_args_string(num):
    l = []
    for n in range(m):
        l.append('?')
    return ', '.join(l)

# Define the Field class. save the database column and type
class Field(object):
    def __init__(self,name,column_type,primary_key,default):
        self.name = name
        self.column_type = column_type
        self.primary_ket = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s, %s>'%(self.__class__.__name__,self.column_type,self.name)

class StringField(Field):
    def __init__(self,name=None,primary_key=False,default=None,
                 ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


class ModelMetaclass(type):

    def __new__(cls,name,bases,attrs):
        if name == 'Model':
            return type.__new__(cls,name,bases,attrs)
        tablename = attrs.get('__table__',None) or name
        logging.info('found model: %s (table:%s)'%(name,tablename))
        mappings = {}
        fields = []
        primarykey = None

        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info(' found mapping: %s==> %s'%(k,v))
                mappings[k] = v
                if v.primary_key :
                    if primarykey:
                        raise AttributeError('Duplicated primary key for field K '%k)
                    primarykey = k
                else:
                    fields.append(k)
        if not primarykey:
            raise AttributeError('primary key not found')

        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f:"`%s`"%f,fields))
        attrs['__mappings__'] = mappings
        attrs['__table__'] = tablename
        attrs['__primary_key__'] = primarykey
        attrs['__fields__'] = fields

        attrs['__select__'] = 'select `%s`,%s from `%s`'%(primarykey,', '.join(escaped_fields),tablename)
        attrs['__insert__'] = 'insert into `%s`(%s,`%s`) values(%s)'%(
            tablename,', '.join(escaped_fields),primarykey,create_args_string(
                len(escaped_fields)+1
            )
        )
        attrs['__update__'] = 'update `%s` set %s where `%s`=?'%(
            tablename,', '.join(lambda f:'`%s`=?'%(mappings.get(f).name or f),fields),
            primarykey
        )
        attrs['__delete__'] = 'delete from `%s` where `%s`=?'%(tablename,
        primarykey)

        return type.__new__(cls,name,bases,attrs)

class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise  AttributeError('Model object has no attribute : %s'%key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self,key):
        return getattr(self,key,None)

    def getValueOrDefault(self,key):
        value = getattr(self,key,None)
        if not value:
            field = self.__mappings__[key]
            value = field.default() if callable(field.default) else field.default
            logging.debug('using default value for %s %s'%(key,str(value)))
            setattr(self,key,value)
        return value

    @classmethod
    async def findAll(cls,where=None,args=None,**kw):
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy',None)
        if orderBy:
            sql.append('orderBy')
            sql.append(orderBy)
        limit = kw.get('limit',None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                sql.append(limit)
            elif isinstance(limit,tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s'%str(limit))
        rs = await select(' '.join(sql),args)
        return [cls(**r) for r in rs]

    @classmethod
    async 