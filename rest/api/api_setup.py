import flask
from flask import Blueprint, g

from authentication.authentication import authentication_provider
from openeoerrors import BadRequest
