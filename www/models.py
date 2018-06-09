#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Models for user, blog, comment
'''

__author__ = 'wangleifu'

import time, uuid

from orm import Model, StringField, IntegerField

def next_id():
	return '%015d%s000' % (int(time.time) * 1000, uuid.uuid4().hex)


class User(Model):
	__table__ = 'users'

	id = IntegerField(primary_key=True)
	name = StringField()

class Blog(Model):
	__table__ = 'blogs'

	pass

class Comment(Model):
	__table__ = 'comments'

	pass