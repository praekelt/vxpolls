vxPolls
=======

Simple PollManager, ResultsManager and PollResultsDashboardServer. The example uses the PollManager only and as a result it doesn't track results yet, however the ResultManager does that for you - it just needs to be hooked up.

Installation
------------

::

	$ virtualenv --no-site-packages ve
	$ source ve/bin/activate
	$ pip install -r requirements.pip

Running
-------

Update `xmpp.yaml` with your GTalk account details and run the following:

::

	$ source ve/bin/activate
	$ supervisord

That will run the necessary processes. Run `supervisorctl` to manage the individual processes.
Your GTalk account should come online, send it a message to start the poll.


Tests
-----

::

	$ source ve/bin/activate
	$ trial tests
