vxPolls
=======

Simple PollManager, ResultsManager and PollResultsDashboardServer. 

Dependencies
------------

#. `RabbitMQ <http://www.rabbitmq.com/>`_

Installation
------------

::

    $ virtualenv --no-site-packages ve
    $ source ve/bin/activate
    $ pip install -r requirements.pip

On initial setup RabbitMQ needs to be configured::

    $ sudo ./ve/src/vumi/utils/rabbitmq.setup.sh

Running
-------

Update `xmpp.yaml` with your GTalk account details and run the following:

::

	$ source ve/bin/activate
	$ supervisord

That will run the necessary processes. Run `supervisorctl` to manage the individual processes.
Your GTalk account should come online, send it a message to start the poll.

You'll find more instructions for dashboards at http://localhost:8101/dashboard/index.html

Tests
-----

::

	$ source ve/bin/activate
	$ trial tests
