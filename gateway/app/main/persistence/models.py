import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Model(db.Model):
    """ Model table that represents the AI Models.
        Columns:
            id (String, Primary Key) : Model's id, used to recover stored model.
            version (String) : Model version.
            checkpoints (ModelCheckPoint) : Model Checkpoints. (One to Many relationship)
            fl_process_id (Integer, ForeignKey) : FLProcess Foreign Key.
    """

    __tablename__ = "__model__"

    id = db.Column(db.String, primary_key=True)
    version = db.Column(db.String())
    checkpoints = db.relationship("ModelCheckPoint", backref="checkpoint")
    fl_process_id = db.Column(
        db.BigInteger, db.ForeignKey("__fl_process__.id"), unique=True
    )

    def __str__(self):
        return f"<Model  id: {self.id}, version: {self.version}>"


class ModelCheckPoint(db.Model):
    """ Model's save points.
        Columns:
            id (Integer, Primary Key): Checkpoint ID.
            values (Binary): Value of the model at a given checkpoint.
            model_id (String, Foreign Key): Model's ID.
    """

    __tablename__ = "__model_checkpoint__"

    id = db.Column(db.BigInteger, primary_key=True)
    values = db.Column(db.LargeBinary)
    model_id = db.Column(db.String, db.ForeignKey("__model__.id"), unique=True)

    @property
    def object(self):
        return sy.serde.deserialize(self.values)

    @object.setter
    def object(self):
        self.data = sy.serde.serialize(self.values)

    def __str__(self):
        return f"<CheckPoint id: {self.id} , values: {self.data}>"


class Plan(db.Model):
    """ Plan table that represents Syft Plans.
        Columns:
            id (Integer, Primary Key): Plan ID.
            value (String): String  (List of operations)
            value_ts (String): String (TorchScript)
            fl_process_id (Integer, Foreign Key) : Referece to FL Process.
    """

    __tablename__ = "__plan__"

    id = db.Column(db.BigInteger, primary_key=True)
    value = db.Column(db.String())
    value_ts = db.Column(db.String())
    fl_process_id = db.Column(db.BigInteger, db.ForeignKey("__fl_process__.id"))

    def __str__(self):
        return (
            f"<Plan id: {self.id}, values: {self.value}, torchscript: {self.value_ts}>"
        )


class Protocol(db.Model):
    """ Protocol table that represents Syft Protocols.
        Columns:
            id (Integer, Primary Key): Protocol ID.
            value: String  (List of operations)
            value_ts: String (TorchScript)
            fl_process_id (Integer, Foreign Key) : Referece to FL Process.
    """

    __tablename__ = "__protocol__"

    id = db.Column(db.BigInteger, primary_key=True)
    value = db.Column(db.String())
    value_ts = db.Column(db.String())
    fl_process_id = db.Column(db.BigInteger, db.ForeignKey("__fl_process__.id"))

    def __str__(self):
        return f"<Protocol id: {self.id}, values: {self.value}, torchscript: {self.value_ts}>"


class Config(db.Model):
    """ Configs table.
        Columns:
            id (Integer, Primary Key): Config ID.
            value (String): Dictionary
            fl_process_id (Integer, Foreign Key) : Referece to FL Process.
    """

    __tablename__ = "__config__"

    id = db.Column(db.BigInteger, primary_key=True)
    config = db.Column(db.PickleType)
    fl_process_id = db.Column(db.BigInteger, db.ForeignKey("__fl_process__.id"))

    def __str__(self):
        return f"<Config id: {self.id} , configs: {self.config}>"


class Cycle(db.Model):
    """ Cycle table.
        Columns:
            id (Integer, Primary Key): Cycle ID.
            start (TIME): Start time.
            sequence (Integer): Cycle's sequence number.
            end (TIME): End time.
            worker_cycles (WorkerCycle): Relationship between workers and cycles (One to many).
            fl_process_id (Integer,ForeignKey): Federated learning ID that owns this cycle.
    """

    __tablename__ = "__cycle__"

    id = db.Column(db.BigInteger, primary_key=True)
    start = db.Column(db.DateTime())
    end = db.Column(db.DateTime())
    sequence = db.Column(db.BigInteger())
    worker_cycles = db.relationship("WorkerCycle", backref="cycle")
    fl_process_id = db.Column(db.BigInteger, db.ForeignKey("__fl_process__.id"))

    def __str__(self):
        return f"< Cycle id : {self.id}, start: {self.start}, end: {self.end}>"


class Worker(db.Model):
    """ Web / Mobile worker table.
        Columns:
            id (String, Primary Key): Worker's ID.
            format_preference (String): either "list" or "ts"
            ping (Int): Ping rate.
            avg_download (Int): Download rate.
            avg_upload (Int): Upload rate.
            worker_cycles (WorkerCycle): Relationship between workers and cycles (One to many).
    """

    __tablename__ = "__worker__"

    id = db.Column(db.String, primary_key=True)
    format_preference = db.Column(db.String())
    ping = db.Column(db.BigInteger)
    avg_download = db.Column(db.BigInteger)
    avg_upload = db.Column(db.BigInteger)
    worker_cycle = db.relationship("WorkerCycle", backref="worker")

    def __str__(self):
        return f"<Worker id: {self.id}, format_preference: {self.format_preference}, ping : {self.ping}, download: {self.download}, upload: {self.upload}>"


class WorkerCycle(db.Model):
    """ Relation between Workers and Cycles.
        Columns:
            id (Integer, Primary Key): Worker Cycle ID.
            fl_process (FLProcess) : FL Process executed during this cycle.
            cycle_id (Integer, ForeignKey): Cycle Foreign key that owns this worker cycle.
            worker_id (String, ForeignKey): Worker Foreign key that owns this worker cycle.
            request_key (String): unique token that permits downloading specific Plans, Protocols, etc.
    """

    __tablename__ = "__worker_cycle__"

    id = db.Column(db.BigInteger, primary_key=True)
    request_key = db.Column(db.String())
    cycle_id = db.Column(db.BigInteger, db.ForeignKey("__cycle__.id"), unique=True)
    worker_id = db.Column(db.String, db.ForeignKey("__worker__.id"), unique=True)

    def __str__(self):
        f"<WorkerCycle id: {self.id}, fl_process: {self.fl_process_id}, cycle: {self.cycle_id}, worker: {self.worker}, request_key: {self.request_key}>"


class FLProcess(db.Model):
    """ Federated Learning Process table.
        Columns:
            id (Integer, Primary Key): Federated Learning Process ID.
            model (Model): Model.
            averaging_plan (Plan): Averaging Plan.
            plans: Generic Plans (such as training plan and validation plan)
            protocols (Protocol) : Generic protocols.
            server_config (Config): Server Configs.
            client_config (Config): Client Configs.
            cycles [Cycles]: FL Cycles.
    """

    __tablename__ = "__fl_process__"

    id = db.Column(db.BigInteger, primary_key=True)
    model = db.relationship("Model", backref="flprocess", uselist=False)
    averaging_plan = db.relationship("Plan", backref="avg_flprocess", uselist=False)
    plans = db.relationship("Plan", backref="plan_flprocess")
    protocols = db.relationship("Protocol", backref="protocol_flprocess")
    server_config = db.relationship("Config", backref="server_flprocess_config")
    client_config = db.relationship("Config", backref="client_flprocess_config")
    cycles = db.relationship("Cycle", backref="cycle_flprocess")

    def __str__(self):
        return f"<FederatedLearningProcess id : {self.id}>"


class GridNodes(db.Model):
    """ Grid Nodes table that represents connected grid nodes.
    
        Columns:
            id (primary_key) : node id, used to recover stored grid nodes (UNIQUE).
            address: Address of grid node.
    """

    __tablename__ = "__gridnode__"

    id = db.Column(db.String(), primary_key=True)
    address = db.Column(db.String())

    def __str__(self):
        return f"< Grid Node {self.id} : {self.address}>"
