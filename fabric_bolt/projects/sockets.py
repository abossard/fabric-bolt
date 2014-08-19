import subprocess
import logging
import signal
import fcntl
import time
import sys
import os

from fabric_bolt.projects.models import Deployment

from socketio.namespace import BaseNamespace
from socketio.sdjango import namespace
from socketio.mixins import RoomsMixin, BroadcastMixin

from threading import Thread

from .util import build_command


@namespace('/deployment')
class DeployNamespace(BaseNamespace, RoomsMixin, BroadcastMixin):

    def initialize(self):
        self.logger = logging.getLogger("socketio.deployment")
        self.log("Socketio session started")

    def log(self, message):
        self.logger.info("[{0}] {1}".format(self.socket.sessid, message))

    def on_join(self, deployment_id):
        self.deployment = Deployment.objects.get(pk=deployment_id)
        if self.deployment.status == self.deployment.PENDING:
            self.update_thread = Thread(target=self.output_stream_generator, args=(self,))
            # self.update_thread.daemon = True
            self.deployment.status = self.deployment.RUNNING
            self.deployment.save()
            self.update_thread.start()

        return True

    def on_input(self, event):
        if event['type'] == 'text':
            try:
                self.process.stdin.write(event['text'] + '\n')
                return True
            except:
                return False
        elif event['type'] == 'abort':
            self.kill_process()

    def recv_disconnect(self):
        self.log('Disconnected')
        self.disconnect(silent=True)
        return True

    def kill_process(self):
        try:
            print "Deployment pid is {}".format(self.deployment.pid)
            os.kill(int(self.deployment.pid), signal.SIGTERM)

            self.broadcast_event('output', {'status': 'running', 'lines': '!!! Aborting... !!!'})
            self.broadcast_event('output', {'status': 'aborted'})

            self.deployment.pid = None
            self.deployment.status = self.deployment.ABORTED
            self.deployment.save()
            return True
        except Exception as e:
            print("Failed to kill... {}".format(e))
            return False

    def output_stream_generator(self, *args, **kwargs):
        cmd = build_command(self.deployment, self.request.session, False),

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            shell=True
        )

        self.deployment.pid = self.process.pid
        self.deployment.save()

        fd = self.process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        self.all_output = ''
        line_count = 0
        while True:
            try:
                nextline = self.process.stdout.read()
            except IOError:
                nextline = ''

            if nextline == '' and self.process.poll() != None:
                break

            self.all_output += nextline
            line_count += 1

            if nextline:
                self.broadcast_event('output', {'status': 'running', 'lines': str(nextline)})
                if line_count > 10:
                    self.deployment.output = self.all_output
                    self.deployment.save()
            time.sleep(0.00001)

            sys.stdout.flush()

        if self.deployment.status != self.deployment.ABORTED:
            self.deployment.status = self.deployment.SUCCESS if self.process.returncode == 0 else self.deployment.FAILED

        self.deployment.output = self.all_output
        self.deployment.pid = None
        self.deployment.save()

        self.broadcast_event('output', {'status': self.deployment.status})
