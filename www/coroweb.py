#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, os, inspect, logging, functools

from urllib import parse
from aiohttp import web
from apis import APIError


def get(path):
	'''
	Define decorate @get('/path')
	'''
	def decorate(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'GET'
		wrapper.__route__  = path
		return wrapper
	return decorate

def post(path):
	'''
	Define decorate @post('/path')
	'''
	def decorate(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__  = path
		return wrapper
	return decorate

def get_requried_kw_args(func):
	args = []
	params = inspect.signature(func).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

def get_named_kw_args(func):
	args = []
	params = inspect.signature(func).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_args(func):
	params = inspect.signature(func).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

def has_var_kw_arg(func):
	params = inspect.signature(func).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_arg(func):
	sig = inspect.signature(func)
	params = sig.parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (param.kind != inspect.Parameter.VAR_POSITION and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function: %s%s' % (func.__name__. str(sig)))
	return found

class RequestHandler(object):

	def __init__(self, app, func):
		self._app  = app
		self._func = func
		self._has_request_arg   = has_request_arg(func)
		self._has_var_kw_arg    = has_var_kw_arg(func)
		self._has_named_kw_args = has_named_kw_args(func)
		self._named_kw_args     = get_named_kw_args(func)
		self._requried_kw_args  = get_requried_kw_args(func)

	async def __call__(self, request):
		kw = None
		if self._has_var_kw_arg or self._has_named_kw_args or self._requried_kw_args:
			if request.method == 'POST':
				if not request.content_type:
					return web.HTTPBadRequest('Missing Content_Type.')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					params = await request.json()
					if not isinstance(params, dict):
						return web.HTTPBadRequest('JSON object must be object.')
					kw = params
				elif ct.startswith('application/x-www-form-urlencode') or ct.startswith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					return web.HTTPBadRequest('Unsupported Content_Type: %s.' % request.content_type)
			if request.method == 'GET':
				qs = request.query_string
				if qs:
					kw = dict()
					for k ,v in parse.parse_qs(qs, True).items():
						kw[k] = v
		if kw == None:
			kw = dict(**request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:
				# remove all unnamed kw:
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copyp[name] = kw[name]
				kw = copy
			# check named arg:
			for k, v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
				kw[k] = v
		if self._has_request_arg:
			kw['request'] = request
		# check requried kw:
		if self._requried_kw_args:
			for name in self._requried_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument: %s' % name)
		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, func):
	method = getattr(func, '__method__', None)
	path = getattr(func, '__route__', None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s' % str(func))
	if not asyncio.iscoroutinefunction(func) and not inspect.isgeneratorfunction(func):
		func = asyncio.coroutine(func)
	logging.info('add route %s %s => %s(%s)' % (method, path, func.__name__, ', '.join(inspect.signature(func).parameters.keys())))
	app.router.add_route(method, path, RequestHandler(app, func))

def add_routes(app, module_name):
	n = module_name.rfind('.')
	if n == (-1):
		mod = __import__(module_name, globals(), locals())
	else:
		name = module_name[n+1:]
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		func = getattr(mod, attr)
		if callable(func):
			method = getattr(func, '__method__', None)
			path = getattr(func, '__route__', None)
			if method and path:
				add_route(app, func)