install_deps:
	apt-get -y install python-pip
	apt-get -y install python-virtualenv
	virtualenv env
	( source env/bin/activate ; pip install -r requirements.txt )
	ln -s /home/matt/regonline_integration/deployment/supervisor supervisor
	update-rc.d supervisor defaults
	/etc/init.d/supervisor start
