#!/usr/bin/env python3
# -*-coding:utf-8-*-

__author__ = 'WuYe'
import asyncio,os,inspect,logging,functools

from urllib import parse
from aiohttp import web
from apis import APIError


def Handler_decorator(path,*,method):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args,**kw):
            return func(*args,**kw)
        wrapper.__router__ = path
        wrapper.__method__ = method
        return wrapper
    return decorator
get = functools.partial(Handler_decorator,method='GET')
post = functools.partial(Handler_decorator,method='POST')

def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY' and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name,param  in params.items():
        if str(param.kind) == "KEWWORD_ONLY":
            args.append(param)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if str(param.kind) == 'KEWWORD_ONLY':
            return True
def has_var_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if str(param.kind) == 'VAR_KEYWORD':
            return True
def has_request_arg(fn):
    params = inspect.signature(fn).parameters
    sig = inspect.signature(fn)
    found = False
    for name,param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (str(param.kind) != "VAR_POSTIONAL" and
                              str(param.kind) != 'KEYWORD_ONLY' and
                          str(param.kind != 'VAR_KEYWORD')):
            raise ValueError('request parameter must be the last parameter in function: %s%s'%(fn.__name__,str(sig)))
    return found

class RequestHandler(object):

    def __init__(self,app,fn):
        self._app = app
        self._fn = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._has_var_kw_args = has_var_kw_args(fn)
        self._has_request_args = has_request_arg(fn)

    async def __call__(self,request):
        kw = None
        if self._has_named_kw_args or self._has_var_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content _type')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params,dict):
                        return web.HTTPBadRequest(text='Json body must be dict')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content_type: %s'%(request.content_type))
            if request.method == 'GET':
                qs = request.query_string # The query string in the URL
                if qs:
                    kw = dict()
                    for k,v in parse.parse_qs(qs,True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_args and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k,v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args:%s'%k)
                kw[k] = v
        if self._has_request_args:
            kw['request'] = request
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s'%name)
        logging.info('call with args: %s'%(str(kw)))

        try:
            r = await self._fn(**kw)
            return r
        except APIError as e:
            return dict(error=e.error,data=e.data,message=e.message)


import inspect,asyncio

def add_route(app,fn):
    method = getattr(fn,'__method__',None)
    path = getattr(fn,'__route__',None)
    if method is None or path is None:
        return ValueError('@get or @post not defined in %s.'%str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s==> %s(%s)'%(method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
    app.router.add_router(method,path,RequestHandler(app,fn))

def add_routes(app,model_name):
    n = model_name.rfind(',')
    if n == -1:
        mod = __import__(model_name,globals(),locals)
    else:
        name = model_name[n+1:]
        mode = getattr(__import__(model_name[:n],globals(),locals(),[name],0),name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod,attr)
        if callable(fn):
            method = getattr(fn,'__method__',None)
            path = getattr(fn,'__route__',None)
            if path and method:
                add_route(app,fn)

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static',path)
    logging.info('add static %s ==> %s'%('/static',path))

