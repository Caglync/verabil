#!/bin/bash
gunicorn --bind=0.0.0.0:8000 --timeout 600 "app:create_app()"
