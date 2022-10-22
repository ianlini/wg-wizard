wg-wizard
=========
.. image:: https://github.com/ianlini/wg-wizard/actions/workflows/main.yml/badge.svg
   :target: https://github.com/ianlini/wg-wizard/actions
.. image:: https://img.shields.io/pypi/v/wg-wizard.svg
   :target: https://pypi.org/project/wg-wizard/
.. image:: https://img.shields.io/pypi/l/wg-wizard.svg
   :target: https://github.com/ianlini/wg-wizard/blob/master/LICENSE
.. image:: https://img.shields.io/github/stars/ianlini/wg-wizard.svg?style=social
   :target: https://github.com/ianlini/wg-wizard

wg-wizard can help you generate the configs for WireGuard interactively,
and control all the server and client configs in a centralized way.

.. contents::

Network Architecture
--------------------

Our default network architecture is one
`relay server <https://docs.sweeting.me/s/wireguard#Bounce-Server>`_
with multiple clients connecting to the VPN via the relay server.

We assume that most people need a network architecture like this.
If you want another architecture, you can still achieve some of them
using the advance configuration.

Why Do We Need wg-wizard
------------------------

TODO

Prerequisite
------------

1. A server with Ubuntu, Debian or Raspberry Pi OS.
   You can still use other Linux distributions,
   but the following instructions might not be applicable.
2. `Install Docker <https://docs.docker.com/engine/install/>`_ on your relay server.
3. `Install Wireguard <https://www.wireguard.com/install/>`_ on your relay server.

Run the Docker Container
------------------------

We use Docker to disable the network to make the whole process secure.

.. code-block:: sh

   # go to the directory you want to put the configs
   # assuming ~/wg-wizard here
   export WG_WIZARD_CONFIG='~/wg-wizard'
   cd "${WG_WIZARD_CONFIG}"
   docker run -it --rm --network=none --volume="$PWD":/workdir ianlini/wg-wizard

Initialize the Configuration
----------------------------

.. code-block:: sh

   # inside the Docker container
   wg-wizard init

Follow the instruction to create the config. Example output:

.. code-block::

   Interface name for WireGuard [wg0]:
   Interface.ListenPort of the relay server [51820]:
   Interface.Address of the relay server [192.168.10.1/24]:
   The default endpoint in clients' Peer.Endpoint configs (e.g., example.com:51280): example.com
   If you want to allow the clients to access the internet via the relay server, you must provide the interface name you want to forward the internet traffic to. It's usually eth0 or wlan0. You can check it by executing `ip addr`. If you provide an interface name {interface}, the following rules will be added:
   - iptables -A FORWARD -i %i -o {interface} -j ACCEPT
   - iptables -A FORWARD -i {interface} -o %i -j ACCEPT
   - iptables -t nat -A POSTROUTING -s {network} -o {interface} -j MASQUERADEInterface name for connecting to the internet []: eth0
   Do you want to allow the clients to connect with each other? If yes, a rule will be added: `iptables -A FORWARD -i %i -o %i -j ACCEPT` [Y/n]:
   Do you want to allow the clients to connect to any IPs on the relay server? If no, only the IP of the WireGuard interface can be connected, that is, the following rules will be added:
   - iptables -A INPUT -d {wg_server_interface_ip} -i %i -j ACCEPT
   - iptables -A INPUT -i %i -j DROP
   [y/N]:
   [2022-10-12 18:41:34,190][INFO] wg_wizard.core: Writing config to /home/pi/pi-gateway/wireguard/wg0.yml
   [2022-10-12 18:41:38,868][INFO] wg_wizard.core: Writing secret to /home/pi/pi-gateway/wireguard/wg0_secret.json

Normally, you can use the default values for almost all of the options.

If you allow the internet access or allow the clients to connect with each other,
you also need to `enable IP forwarding <https://www.digitalocean.com/community/tutorials/how-to-set-up-wireguard-on-ubuntu-20-04#step-4-adjusting-the-wireguard-server-s-network-configuration>`_.

For convenience, in the following instructions,
we assume that your WireGuard interface name is ``wg0``:

.. code-block:: sh

   export WG_INTERFACE=wg0

Add a Peer
----------

.. code-block:: sh

   # inside the Docker container
   wg-wizard add-peer

Follow the instruction to create the peer config. Example output:

.. code-block::

   Interface name for WireGuard [wg0]:
   Name of the client: phone1
   Peer.PersistentKeepalive of the client [25]:
   Interface.Address of the client [192.168.10.2/32]:
   Peer.AllowedIPs of the client [0.0.0.0/0, ::/0]:
   [2022-10-04 16:40:01,337][INFO] wg_wizard.core: Writing config to /workdir/wg0.yml
   [2022-10-04 16:40:01,358][INFO] wg_wizard.core: Writing secret to /workdir/wg0_secret.json
   [2022-10-04 16:40:01,362][INFO] wg_wizard.cli: Client's wg-quick config QR Code:
   ...

Normally, you can use the default values for almost all of the options.
In the end, there will be a QR Code generated.
You can now use your `WireGuard app <https://www.wireguard.com/install/>`_
on your phone to scan the QR Code to import the config.
If your client doesn't support QR Code, you can use another command to generate the text:

.. code-block:: sh

   wg-wizard export-client-config --interface "${WG_INTERFACE}" --name phone1 --no-qrcode

Set Up the WireGuard Server
---------------------------

Preparing:

.. code-block:: sh

   # on your relay server (outside the Docker container)
   cd "${WG_WIZARD_CONFIG}"
   export WG_INTERFACE=wg0  # replace wg0 with your interface name
   (umask 077; sudo mkdir /etc/wireguard/)

Exporting server config:

.. code-block:: sh

   docker run --rm --network=none --volume="$PWD":/workdir ianlini/wg-wizard \
       wg-wizard export-server-config -i "${WG_INTERFACE}" \
       | sudo cp --backup /dev/stdin "/etc/wireguard/${WG_INTERFACE}.conf"

If you haven't enabled the service:

.. code-block:: sh

   # start the WireGuard server
   sudo systemctl enable "wg-quick@${WG_INTERFACE}.service"
   sudo systemctl start "wg-quick@${WG_INTERFACE}.service"

Now you can turn on the WireGuard tunnel on your client (phone1),
and it should work.

If the service is already running, you can check the config diff first:

.. code-block:: sh

   sudo diff "/etc/wireguard/${WG_INTERFACE}.conf~" "/etc/wireguard/${WG_INTERFACE}.conf"

After confirming the changes, there are 2 ways to apply them.

1. If you are not changing the wg-quick specific interface configs
   (e.g., Address, DNS, MTU, Table, PreUp, PostUp, PreDown,
   PostDown and SaveConfig),
   you can reload the config without stopping the server:

   .. code-block:: sh

      sudo systemctl reload "wg-quick@${WG_INTERFACE}.service"

2. Otherwise, you should restart the server:

   .. code-block:: sh

      sudo systemctl restart "wg-quick@${WG_INTERFACE}.service"


Troubleshooting
---------------

Read the service log:

.. code-block:: sh

   journalctl -u "wg-quick@${WG_INTERFACE}.service" -f -n 1000

Enable the kernel log:

.. code-block:: sh

   sudo modprobe wireguard
   echo module wireguard +p | sudo tee /sys/kernel/debug/dynamic_debug/control

Read the kernel log:

.. code-block:: sh

   journalctl -k -f -n 1000 | grep wireguard

Debug iptables:

.. code-block:: sh

   # trace the ICMP packets from a WireGuard client
   sudo iptables -t raw -A PREROUTING -i "${WG_INTERFACE}" -p icmp -j TRACE
   # trace the incoming ICMP packets from the internet to a WireGuard client
   sudo iptables -t mangle -A FORWARD -d 192.168.10.0/24 -p icmp -j TRACE

.. warning::
   Debugging iptables requires much more knowledge,
   or you might generate large logs,
   or even break the network of the whole machine.
   However, it is highly possible that the generated configs don't work out-of-the-box.
   It is the hard part when developing this tool because people will have different existing rules.
   If you have a bad luck, you might need to spend some time understanding
   the relationship between iptables and WireGuard.

Build the Docker Image from Scratch
-----------------------------------

TODO

.. code-block:: sh

   git clone ...
   cd ...
   docker build . -t ianlini/wg-wizard

References
----------

- `Some Unofficial WireGuard Documentation <https://docs.sweeting.me/s/wireguard>`_
- `How To Set Up WireGuard on Ubuntu 20.04 <https://www.digitalocean.com/community/tutorials/how-to-set-up-wireguard-on-ubuntu-20-04>`_
- `How To Set Up WireGuard Firewall Rules in Linux <https://www.cyberciti.biz/faq/how-to-set-up-wireguard-firewall-rules-in-linux/>`_
