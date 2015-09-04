# Copyright ClusterHQ Inc.  See LICENSE file for details.

"""
Tests for the datasets REST API.
"""

from uuid import UUID, uuid4

from twisted.internet.task import deferLater
from twisted.trial.unittest import TestCase
from twisted.internet import reactor

from docker.utils import create_host_config

from ...testtools import random_name
from ..testtools import (
    require_cluster, require_moving_backend, create_dataset,
    REALISTIC_BLOCKDEVICE_SIZE, get_docker_client,
    post_http_server, query_http_server, assert_http_server,
)

from ..scripts import SCRIPTS


class LeaseAPITests(TestCase):
    """
    Tests for the leases API.
    """
    @require_moving_backend
    @require_cluster(2)
    def test_lease_prevents_move(self, cluster):
        """
        A dataset cannot be moved if a lease is held on
        it by a particular node.
        """
        http_port = 8080
        dataset_id = uuid4()
        client = get_docker_client(cluster, cluster.nodes[0].public_address)
        d = create_dataset(
            self, cluster, maximum_size=REALISTIC_BLOCKDEVICE_SIZE,
            dataset_id=dataset_id
        )

        def acquire_lease(dataset):
            # Call the API to acquire a lease with the dataset ID.
            acquiring_lease = cluster.client.acquire_lease(
                dataset.dataset_id, UUID(cluster.nodes[0].uuid), expires=1000)

            def get_dataset_path(lease, created_dataset):
                # import pdb;pdb.set_trace()
                get_leases = cluster.client.list_leases()
                def check_leases(leases):
                    #import pdb;pdb.set_trace()
                    pass
                get_leases.addCallback(check_leases)
                getting_datasets = cluster.client.list_datasets_state()

                def extract_dataset_path(datasets):
                    return datasets[0].path

                getting_datasets.addCallback(extract_dataset_path)
                return getting_datasets

            acquiring_lease.addCallback(get_dataset_path, dataset)
            return acquiring_lease

        d.addCallback(acquire_lease)

        def start_http_container(dataset_path, client):
            # Launch data HTTP container and make POST requests
            # to it in a looping call every second.
            # return looping call deferred
            script = SCRIPTS.child("datahttp.py")
            script_arguments = [u"/data"]
            docker_arguments = {
                "host_config": create_host_config(
                    binds=["{}:/data".format(dataset_path.path)],
                    port_bindings={http_port: http_port}),
                "ports": [http_port],
                "volumes": [u"/data"]}
            container = client.create_container(
                "python:2.7-slim",
                ["python", "-c", script.getContent()] + list(script_arguments),
                **docker_arguments)
            cid = container["Id"]
            client.start(container=cid)
            self.addCleanup(client.remove_container, cid, force=True)
            return cid

        d.addCallback(start_http_container, client)

        def write_data(container_id):
            data = random_name(self).encode("utf-8")
            writing = post_http_server(
                self, cluster.nodes[0].public_address, http_port,
                {"data": data}
            )
            writing.addCallback(
                lambda _: assert_http_server(
                    self, cluster.nodes[0].public_address,
                    http_port, expected_response=data
                )
            )

            def check_leases_again(_):
                get_leases = cluster.client.list_leases()
                def check_leases(leases):
                    import pdb;pdb.set_trace()
                    pass
                get_leases.addCallback(check_leases)
                return get_leases

            writing.addCallback(check_leases_again)
            writing.addCallback(lambda _: container_id)
            return writing

        d.addCallback(write_data)

        def stop_container(container_id, client, dataset_id):
            # This ensures Docker hasn't got a lock on the volume that
            # might prevent it being moved separate to the lock held by
            # the lease.
            primary = cluster.nodes[1].uuid
            client.stop(container_id)
            #move_dataset_request = cluster.client.move_dataset(
            #    primary, dataset_id)
            #move_dataset_request.addCallback(lambda _: container_id)
            #return move_dataset_request
            return container_id

        d.addCallback(stop_container, client, dataset_id)

        def wait_five_seconds(container_id):
            return deferLater(reactor, 5, lambda: container_id)

        d.addCallback(wait_five_seconds)

        def restart_container(container_id, client):
            client.start(container=container_id)
            return container_id

        d.addCallback(restart_container, client)

        d.addCallback(write_data)

        def stop_container_again(container_id, client, dataset_id):
            client.stop(container_id)
            get_leases = cluster.client.list_leases()
            def got_leases(leases):
                import pdb;pdb.set_trace()
            get_leases.addCallback(got_leases)
            return get_leases
            # import pdb;pdb.set_trace()
            #releasing = cluster.client.release_lease(dataset_id)
            #releasing.addCallback(lambda _: container_id)
            #return releasing

        d.addCallback(stop_container_again, client, dataset_id)

        d.addCallback(wait_five_seconds)

        d.addCallback(restart_container, client)

        def container_no_start(_):
            import pdb;pdb.set_trace()

        d.addBoth(container_no_start)

        return d

        """
        def request_move_dataset(self):
            # We can then request to move the dataset attached to the container.
            return deferred

        def wait_some_amount_of_time(self):
            # Because the dataset is leased, we should be able to continue
            # writing data via HTTP requests to the running container.
            # We should be able to do this for some number of seconds.
            # The looping call running in parallel to this is continuing to
            # write data.

            # wait some time and return a deferred

        def stop_container(self):
            # We stop the container, so that there is no constraint outside
            # of leases to prevent the volume from being unmounted.

            def confirmed_stopped(self):
                # When the container is confirmed as stopped,
                # restart the container again, to prove the dataset
                # hasn't moved.
                # If the dataset had moved, the host path on the volume would
                # have been unmounted. # XXX is this actually true, does
                # Flocker remove mountpoint directories?

        def stop_container_again(self):
            # Stop the container again.

            def stopped_again(self):
                # Ask for the lease to be released, causing the dataset to move.
                # Wait a couple of seconds.

        def try_to_start_again(self):
            # After a couple of seconds, we can try to recreate the container
            # and that should fail, because the host mount path for the volume
            # should no longer exist.
        """
        self.fail("not implemented yet")

    @require_moving_backend
    @require_cluster(2)
    def test_lease_prevents_delete(self, cluster):
        """
        A dataset cannot be deleted if a lease is held on
        it by a particular node.
        """
        self.fail("not implemented yet")

    @require_moving_backend
    @require_cluster(2)
    def test_delete_dataset_after_lease_release(self, cluster):
        """
        A dataset can be deleted once a lease held on it by a
        particular node is released.
        """
        self.fail("not implemented yet")

    @require_moving_backend
    @require_cluster(2)
    def test_delete_dataset_after_lease_expiry(self, cluster):
        """
        A dataset can be deleted once a lease held on it by a
        particular node has expired.
        """
        self.fail("not implemented yet")
