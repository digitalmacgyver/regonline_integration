install_deps:
	apt-get -y install python-pip
	apt-get -y install python-virtualenv
	virtualenv env
	( source env/bin/activate ; pip install -r requirements.txt )
