install_deps:
	apt-get -y install python-pip
	apt-get -y install python-virtualenv
	apt-get -y install nginx
	virtualenv env
	( source env/bin/activate ; pip install -r requirements.txt )
	ln -s /home/matt/regonline_integration/config/abi.conf /etc/nginx/sites-enabled/abi.conf
	ln -s /home/matt/regonline_integration/deployment/supervisor /etc/init.d/supervisor
	update-rc.d supervisor defaults
	/etc/init.d/supervisor start
	/etc/init.d/nginx restart
