#!/bin/sh
# One-off mirror script; credentials inline (a real-world anti-pattern).
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY aws s3 sync s3://rs-pilot-legacy-downloads ./mirror
