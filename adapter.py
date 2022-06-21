#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BioCypher - CROssBAR prototype
"""

import json
import os
import yaml
import importlib as imp

import biocypher


class BiocypherAdapter:
    """
    The connection can be defined in three ways:
        * Providing a ready ``neo4j.Driver`` instance
        * By URI and authentication data
        * By a YML config file

    Args:
        driver (neo4j.Driver): A ``neo4j.Driver`` instance, created by,
            for example, ``neo4j.GraphDatabase.driver``.
        db_name (str): Name of the database (Neo4j graph) to use.
        db_uri (str): Protocol, host and port to access the Neo4j server.
        db_auth (tuple): Neo4j server authentication data: tuple of user
            name and password.
        config_file (str): Path to a YML config file which provides the URI,
            user name and password.
        network (pypath.core.network.Network): A network database object.
        wipe (bool): Wipe the database after connection, ensuring the data
            is loaded into an empty database.
    """

    def __init__(
        self,
        driver=None,
        db_name="neo4j",
        db_uri="bolt://localhost:7687",
        db_auth=("neo4j", "your_password_here"),
        config_file="/config/module_config.yaml",
        network=None,
        wipe=False,
    ):

        self.bcy = biocypher.Driver(
            driver=driver,
            db_name=db_name,
            db_uri=db_uri,
            db_auth=db_auth,
            config_file=config_file,
            wipe=wipe,
        )

        if network:

            self.set_network(network)

    def set_network(self, network):

        self.network = network

    def build_python_object(self):
        """
        Load CROssBAR example data.
        """

        with open("CROssBAR_Web-service_Example_1.json", "r") as file:
            crossbar_graph = json.load(file)

        self.set_network(crossbar_graph)

    def translate_python_object_to_neo4j(self, network=None):
        """
        Loads a pypath network into the biocypher (Neo4j) backend.

        Args:
            - network (pypath.core.network.Network): A network database
              object. If `None`, the value of :py:attr:`network` will be
              used.
        """

        network = network or self.network
        if not network:

            self._log("No network provided.")
            return

        def gen_nodes(nodes):
            for n in nodes:
                if len(n["data"]) == 3:
                    _id = self._process_id(n["data"]["id"])
                    _type = self._process_type(
                        n["data"]["id"], n["data"]["Node_Type"]
                    )
                    _props = {"display_name": str(n["data"]["display_name"])}
                    yield (_id, _type, _props)

                elif len(n["data"]) == 4:
                    _id = self._process_id(n["data"]["id"])
                    _type = self._process_type(
                        n["data"]["id"], n["data"]["Node_Type"]
                    )

                    _props = {
                        "display_name": str(n["data"]["display_name"]),
                        "enrich_score": str(n["data"]["enrichScore"]),
                    }
                    yield (_id, _type, _props)

        id_type_tuples = gen_nodes(list(network["nodes"]))
        # print(next(id_type_tuples))
        self.bcy.add_nodes(id_type_tuples)

        def gen_edges(edges):
            types_dict = {
                "interacts w/": "Interacts_With",
                "is associated w/": "Is_Associated_With",
                "is related to": "Is_Related_To",
                "targets": "Targets",
                "is involved in": "Is_Involved_In",
                "indicates": "Indicates",
                "modulates": "Modulates",
            }
            for e in edges:
                _source = self._process_id(e["data"]["source"])
                _target = self._process_id(e["data"]["target"])
                _type = types_dict[str(e["data"]["label"])]
                _props = {"Edge_Type": e["data"]["Edge_Type"]}
                yield (_source, _target, _type, _props)

        src_tar_type_tuples = list(gen_edges(list(network["edges"])))
        # self.bcy.add_edges(src_tar_type_tuples)

    def write_to_csv_for_admin_import(self, network=None, db_name=None):
        """
        Loads a pypath network into the biocypher (Neo4j) backend using
        the fast Admin Import function, which requires text files that
        need to be properly formatted since it turns off safety measures
        at import.

        Args:
            - network (pypath.core.network.Network): A network database
              object. If `None`, the value of :py:attr:`network` will be
              used.
        """

        network = network or self.network

        if not network:
            self._log("No network provided.")
            return

        # write nodes
        def gen_nodes(nodes):
            for n in nodes:
                id = self._process_id(n.identifier)
                type = n.entity_type
                props = {"taxon": n.taxon, "label": n.label}
                print(props)
                yield (id, type, props)

        id_type_tuples = gen_nodes(network.nodes.values())

        self.bcy.write_nodes(id_type_tuples, db_name=db_name)

        # write edges
        def gen_edges(edges):
            for e in edges:
                src = self._process_id(e.id_a)
                tar = self._process_id(e.id_b)
                type = e.type
                props = {"effect": e.effect, "directed": e.directed}
                yield (src, tar, type, props)

        src_tar_type_tuples = gen_edges(network.generate_df_records())

        self.bcy.write_edges(src_tar_type_tuples, db_name=db_name)

        self.bcy.write_import_call()

    def _process_id(self, identifier):
        """
        Replace critical symbols in ids so that neo4j doesn't throw
        a type error.
        """
        identifier = str(identifier)

        """
        replace_characters = [':', '-']
        
        for character in replace_characters:            
            if character in identifier:
                identifier = identifier.replace(character, "_")
        """

        return identifier

    def _process_type(self, _id, _type):
        """
        Processes the type of a node or edge.
        """

        if _type == "kegg_Disease":
            _type = "KEGG.DISEASE"

        if _type == "Disease":
            if ":" in _id:
                _type = _id.split(":")[0]

        if _type.endswith("_N"):
            _type = str(_type).replace("_N", "").capitalize()

        if _type == "Prediction":
            _type = "Compound"

        return _type

    def load(self, obj):
        """
        Loads any compatible object into the biocypher (Neo4j) database.

        Args:
            obj: An object from this module compatible with the current
                adapter. Currently the following database objects are
                supported:
                    * :py:class:`pypath.core.network.Network`
        """

        if hasattr(obj, "nodes") and hasattr(obj, "interactions"):

            self.translate_python_object_to_neo4j(network=obj)
