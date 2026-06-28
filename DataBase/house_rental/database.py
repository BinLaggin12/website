from cassandra.query import BatchStatement, SimpleStatement
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel
import json
import uuid
import enum
import asyncio
import random
from dataclasses import dataclass

KEYSPACE = "house_rental"
DEBUG = False


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


class RentalStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


@dataclass
class Rental:
    rental_id: uuid.UUID
    user_id: uuid.UUID
    house_id: uuid.UUID
    created_at: str
    status: RentalStatus
    data: dict


@dataclass
class PreparedStatements:
    make_rental_lock: SimpleStatement
    make_rental_lock_if_cancelled: SimpleStatement
    make_rental_bump_ttl: SimpleStatement
    insert_rental: SimpleStatement
    insert_rental_by_user: SimpleStatement
    update_rental: SimpleStatement
    update_rental_by_user: SimpleStatement
    cancel_rental: SimpleStatement
    cancel_rental_by_user: SimpleStatement
    cancel_rental_lock: SimpleStatement


class Database:
    def __init__(self):
        self.cluster = Cluster(["127.0.0.1", "127.0.0.2", "127.0.0.3"])
        self.session = self.cluster.connect()
        self._create_schema()
        self.prepared_statements: PreparedStatements = self._prepare_statements()

    def _create_schema(self):
        s = f"""
                CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
                WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': '2'}}
            """
        self.session.execute(SimpleStatement(s))

        self.session.execute(
            SimpleStatement(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.houses (
                    id uuid,
                    name text,
                    address text,
                    PRIMARY KEY (id)
                )
                """)
        )
        self.session.execute(
            SimpleStatement(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.users (
                    id uuid,
                    name text,
                    PRIMARY KEY (id)
                )
                """)
        )
        self.session.execute(
            SimpleStatement(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.house_rentals (
                    rental_id uuid,
                    user_id uuid,
                    house_id uuid,
                    created_at timestamp,
                    status text,
                    data text,
                    PRIMARY KEY (rental_id)
                )
                """)
        )
        self.session.execute(
            SimpleStatement(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.house_rentals_by_user (
                    rental_id uuid,
                    user_id uuid,
                    house_id uuid,
                    created_at timestamp,
                    status text,
                    data text,
                    PRIMARY KEY ((user_id), rental_id)
                )
                """)
        )
        self.session.execute(
            SimpleStatement(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.rental_locks (
                    house_id uuid,
                    user_id uuid,
                    status text,
                    PRIMARY KEY (house_id)
                )
                """)
        )

        debug_print("Schema created successfully.")

    def _now(self):
        from datetime import datetime

        return datetime.now()

    def _prepare_statements(self):
        return PreparedStatements(
            make_rental_lock=SimpleStatement("""
                INSERT INTO house_rental.rental_locks (house_id, user_id, status)
                VALUES (%s, %s, 'active')
                IF NOT EXISTS
                USING TTL 60;
            """),
            make_rental_lock_if_cancelled=SimpleStatement("""
                UPDATE house_rental.rental_locks
                USING TTL 60
                SET status='active', user_id=%s
                WHERE house_id=%s IF status = 'cancelled';
            """),
            make_rental_bump_ttl=SimpleStatement("""
                UPDATE house_rental.rental_locks
                SET status = 'active', user_id = %s
                WHERE house_id=%s
                IF user_id = %s;
            """),
            insert_rental=SimpleStatement("""
                INSERT INTO house_rental.house_rentals
                (rental_id,user_id,house_id,created_at,status,data)
                VALUES (%s, %s, %s, %s, %s, %s);
            """),
            insert_rental_by_user=SimpleStatement("""
                INSERT INTO house_rental.house_rentals_by_user
                (rental_id,user_id,house_id,created_at,status,data)
                VALUES (%s, %s, %s, %s, %s, %s);
            """),
            update_rental=SimpleStatement("""
                UPDATE house_rental.house_rentals
                SET data=%s
                WHERE rental_id=%s
            """),
            update_rental_by_user=SimpleStatement("""
                UPDATE house_rental.house_rentals_by_user
                SET data=%s
                WHERE user_id=%s AND rental_id=%s
            """),
            cancel_rental=SimpleStatement("""
                UPDATE house_rental.house_rentals
                USING TTL 2592000
                SET status='cancelled', user_id=null
                WHERE rental_id=%s;
            """),
            cancel_rental_by_user=SimpleStatement("""
                UPDATE house_rental.house_rentals_by_user
                USING TTL 2592000
                SET status='cancelled'
                WHERE user_id=%s AND rental_id=%s;
            """),
            cancel_rental_lock=SimpleStatement("""
                UPDATE house_rental.rental_locks
                USING TTL 2592000
                SET status='cancelled', user_id=null
                WHERE house_id=%s;
            """),
        )

    async def _execute_async(self, query, params=None, *, op_id=None):
        """Wrap cassandra futures into asyncio futures so that
        we can use async/await.
        """
        future = self.session.execute_async(query, params)
        loop = asyncio.get_running_loop()

        asyncio_future = loop.create_future()

        def handle_success(rows):
            loop.call_soon_threadsafe(asyncio_future.set_result, rows)

        def handle_error(exception):
            loop.call_soon_threadsafe(asyncio_future.set_exception, exception)

        future.add_callbacks(handle_success, handle_error)
        try:
            f = await asyncio_future
            debug_print(f"execute_async({op_id=}, {query=}, {params=}) = {f}")
            return f
        except Exception as e:
            debug_print(
                f"execute_async({op_id=}, {query=}, {params=}): Exception occurred: {e}"
            )
            raise

    async def _run_with_exponential_backoff(
        self,
        coro_factory,
        *,
        max_retries=10,
        initial_delay=0.1,
        op_id=None,
        op_name=None,
    ):
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                debug_print(
                    f"_run_with_exponential_backoff({op_id=}, {op_name=}): attempt {attempt + 1}/{max_retries}, delay={delay:.2f}s"
                )
                return await coro_factory()
            except Exception as e:
                debug_print(
                    f"_run_with_exponential_backoff({op_id=}, {op_name=}): attempt {attempt + 1}/{max_retries}: Exception occurred: {e}"
                )
                if attempt == max_retries - 1:
                    raise
                jitter = random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay + jitter)
                delay *= 2

    async def _make_rental_acquire_lock(
        self,
        *,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        op_id: int,
    ):
        # Lock the rental
        debug_print(
            f"_make_rental_acquire_lock({op_id=}): Trying to acquire lock for house_id={house_id} and user_id={user_id}"
        )
        try:
            result = await self._execute_async(
                # INSERT INTO house_rental.rental_locks (house_id, user_id, status)
                # VALUES (%s, %s, 'active')
                # IF NOT EXISTS
                # USING TTL 60;
                self.prepared_statements.make_rental_lock,
                (house_id, user_id),
                op_id=op_id,
            )
        except Exception as e:
            debug_print(f"_make_rental_acquire_lock({op_id=}): INSERT path failed")
            raise

        if not result[0].applied:
            # Maybe it is only cancelled ... try only locking
            # with IF status = 'cancelled'.

            if result[0].status != "cancelled":
                # don't bother - it's already active.
                debug_print(
                    f"_make_rental_acquire_lock({op_id=}): Lock already exists for house_id={house_id} and is active, cannot acquire lock for user_id={user_id}"
                )
                return False

            # is cancelled - use IF anyway to avoid race conditions.
            debug_print(
                f"_make_rental_acquire_lock({op_id=}): Lock already exists for house_id={house_id}, trying to acquire if cancelled"
            )
            try:
                result = await self._execute_async(
                    # UPDATE house_rental.rental_locks
                    # USING TTL 60
                    # SET status='active', user_id=%s
                    # WHERE house_id=%s IF status = 'cancelled';
                    self.prepared_statements.make_rental_lock_if_cancelled,
                    (user_id, house_id),
                    op_id=op_id,
                )
            except Exception as e:
                debug_print(f"_make_rental_acquire_lock({op_id=}): UPDATE path failed")
                raise

            if not result[0].applied:
                debug_print(
                    f"_make_rental_acquire_lock({op_id=}): Failed to acquire lock for house_id={house_id}, user_id={user_id}"
                )
                return False

        return True

    async def _make_rental_insert_rental(
        self,
        *,
        op_id: int,
        rental_id: uuid.UUID,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        created_at,
        data_object,
    ):
        data = json.dumps(data_object)

        # Result doesn't exist or is cancelled --> OK, we have the lock
        # and can fill everything else.
        debug_print(
            f"_make_rental_insert_rental({op_id=}): Acquired lock for house_id={house_id}, user_id={user_id}, inserting rental"
        )
        batch = BatchStatement()

        batch.add(
            self.prepared_statements.insert_rental,
            (rental_id, user_id, house_id, created_at, RentalStatus.ACTIVE.value, data),
        )

        batch.add(
            self.prepared_statements.insert_rental_by_user,
            (rental_id, user_id, house_id, created_at, RentalStatus.ACTIVE.value, data),
        )

        await self._execute_async(batch, op_id=op_id)

        debug_print(
            f"_make_rental_insert_rental({op_id=}): Inserted rental for house_id={house_id}, user_id={user_id}"
        )

    async def _make_rental_bump_ttl(
        self,
        *,
        op_id: int,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
    ):
        # Bump TTL of the lock after everything is OK
        await self._execute_async(
            self.prepared_statements.make_rental_bump_ttl,
            (user_id, house_id, user_id),
            op_id=op_id,
        )

        debug_print(
            f"_make_rental_bump_ttl({op_id=}): Bumped TTL of lock after successful rental creation"
        )
        return True

    async def make_rental(
        self,
        *,
        rental_id: uuid.UUID,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        data_object,
    ):
        op_id = random.randint(1, 1000000)
        # FIXME: This is still not robust to "CAS operation result unknown" errors
        # and may cause this function return False even if the lock was acquired
        # (but the rest of rental data is not written).
        #
        # Consider the following scenario:
        # - acquire lock throws with unknown (1700) but actually inserts the lock
        # - we will repeat the operation and fail to acquire the lock, even though we actually have it.
        # This is the source of missing rentals in stress test 3 ("n_successes_per_house.0" > 0)
        #
        # To fix this we would need to get to know the actual lock state
        # in a reliable and race-condition-free way and return it here
        # instead of just naively repeating and obviously failing.
        c = await self._run_with_exponential_backoff(
            lambda: self._make_rental_acquire_lock(
                op_id=op_id,
                user_id=user_id,
                house_id=house_id,
            ),
            op_id=op_id,
            op_name="make_rental_acquire_lock",
        )
        if not c:
            debug_print(
                f"make_rental: Failed to acquire lock for user_id={user_id}, house_id={house_id}"
            )
            return False

        await self._run_with_exponential_backoff(
            lambda: self._make_rental_insert_rental(
                op_id=op_id,
                rental_id=rental_id,
                user_id=user_id,
                house_id=house_id,
                created_at=self._now(),
                data_object=data_object,
            ),
            op_id=op_id,
            op_name="make_rental_insert_rental",
        )

        await self._run_with_exponential_backoff(
            lambda: self._make_rental_bump_ttl(
                op_id=op_id,
                user_id=user_id,
                house_id=house_id,
            ),
            op_id=op_id,
            op_name="make_rental_bump_ttl",
        )

        return c

    def update_rental(
        self,
        *,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        rental_id: uuid.UUID,
        data_object,
    ):
        data = json.dumps(data_object)

        # Update the rental
        batch = BatchStatement()

        batch.add(
            self.prepared_statements.update_rental,
            (data, rental_id),
        )

        batch.add(
            self.prepared_statements.update_rental_by_user,
            (data, user_id, rental_id),
        )

        self.session.execute(batch)

    def get_current_lock(self, house_id: uuid.UUID):
        q = """
        SELECT user_id, status
        FROM house_rental.rental_locks
        WHERE house_id=%s
        """

        # execute with consistency SERIAL to be sure we see the most recent state of the lock
        x = self.session.execute(
            SimpleStatement(q, consistency_level=ConsistencyLevel.SERIAL), (house_id,)
        )
        row = x.one()
        if not row:
            return None
        if row.status == "cancelled":
            return None
        return row.user_id if row else None

    def get_rental(self, rental_id: uuid.UUID):
        q = """
        SELECT rental_id, user_id, house_id, created_at, status, data
        FROM house_rental.house_rentals
        WHERE rental_id=%s
        """
        x = self.session.execute(SimpleStatement(q), (rental_id,))
        row = x.one()
        if not row:
            return None

        return Rental(
            rental_id=row.rental_id,
            user_id=row.user_id,
            house_id=row.house_id,
            created_at=row.created_at,
            status=RentalStatus(row.status),
            data=json.loads(row.data),
        )

    def list_rentals_by_user(self, user_id: uuid.UUID):
        q = """
        SELECT rental_id, house_id, created_at, status, data
        FROM house_rental.house_rentals_by_user
        WHERE user_id=%s
        """
        x = self.session.execute(SimpleStatement(q), (user_id,))

        # -> dataclass
        return [
            Rental(
                rental_id=row.rental_id,
                user_id=user_id,
                house_id=row.house_id,
                created_at=row.created_at,
                status=RentalStatus(row.status),
                data=json.loads(row.data),
            )
            for row in x
        ]

    async def _cancel_rental_impl(
        self,
        *,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        rental_id: uuid.UUID,
    ):
        batch = BatchStatement()

        batch.add(
            self.prepared_statements.cancel_rental,
            (rental_id,),
        )

        batch.add(
            self.prepared_statements.cancel_rental_by_user,
            (user_id, rental_id),
        )

        batch.add(
            self.prepared_statements.cancel_rental_lock,
            (house_id,),
        )

        await self._execute_async(batch)

    async def cancel_rental(
        self,
        *,
        user_id: uuid.UUID,
        house_id: uuid.UUID,
        rental_id: uuid.UUID,
    ):
        await self._run_with_exponential_backoff(
            lambda: self._cancel_rental_impl(
                user_id=user_id,
                house_id=house_id,
                rental_id=rental_id,
            )
        )

    def truncate_all(self):
        self.session.execute(SimpleStatement("TRUNCATE house_rental.rental_locks"))
        self.session.execute(SimpleStatement("TRUNCATE house_rental.house_rentals"))
        self.session.execute(
            SimpleStatement("TRUNCATE house_rental.house_rentals_by_user")
        )
