install_deps:
	virtualenv env
	( source env/bin/activate ; pip install -r requirements.txt )
