import asyncio
import time
import uuid
import random
import sys
import multiprocessing
from .database import Database


def get_db():
    return Database()


########


def requests_stats(request_times):
    sorted_times = sorted(request_times)
    n = len(sorted_times)
    median = sorted_times[n // 2] if n > 0 else 0
    p99 = sorted_times[int(n * 0.99)] if n > 0 else 0
    average = sum(sorted_times) / n if n > 0 else 0
    return {
        "average": average,
        "median": median,
        "p99": p99,
    }


########


async def run_stress_test(
    test_logic_callback, n_requests=5000, concurrency=200, items=None
):
    if items is None:
        items = range(n_requests)

    sem = asyncio.Semaphore(concurrency)

    async def wrapped_item(item):
        async with sem:
            await test_logic_callback(item)

    tasks = [wrapped_item(item) for item in items]
    await asyncio.gather(*tasks)


########


# Stress Test 1: The client makes the same request very quickly.
def stress_test_1_rent_separate_homes():
    user_id = uuid.uuid4()
    db_connections = {}

    def get_db_for_user(uid):
        if uid not in db_connections:
            db_connections[uid] = get_db()
        return db_connections[uid]

    db = get_db_for_user(user_id)

    data = {
        "n_requests": 0,
        "n_errors": 0,
    }

    request_times = []

    async def test(_idx):
        house_id = uuid.uuid4()

        start_time = time.perf_counter()
        try:
            result = await db.make_rental(
                rental_id=uuid.uuid4(),
                user_id=user_id,
                house_id=house_id,
                data_object={"some": "data"},
            )
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)

            data["n_requests"] += 1
            if not result:
                data["n_errors"] += 1
        except Exception as e:
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            data["n_requests"] += 1
            data["n_errors"] += 1
            print(f"Error in make_rental: {e}")

    asyncio.run(run_stress_test(test))

    data["request_stats"] = requests_stats(request_times)

    return data


def stress_test_1_rent_same_home():
    user_id = uuid.uuid4()
    house_id = uuid.uuid4()
    db_connections = {}

    def get_db_for_user(uid):
        if uid not in db_connections:
            db_connections[uid] = get_db()
        return db_connections[uid]

    db = get_db_for_user(user_id)

    data = {
        "n_requests": 0,
        "n_failed_rentals": 0,
        "n_errors": 0,
    }

    request_times = []

    async def test(_idx):
        start_time = time.perf_counter()
        try:
            result = await db.make_rental(
                rental_id=uuid.uuid4(),
                user_id=user_id,
                house_id=house_id,
                data_object={"some": "data"},
            )
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)

            data["n_requests"] += 1
            if not result:
                data["n_failed_rentals"] += 1
        except Exception as e:
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            data["n_requests"] += 1
            data["n_errors"] += 1
            print(f"Error in make_rental: {e}")

    asyncio.run(run_stress_test(test, n_requests=5000))

    data["request_stats"] = requests_stats(request_times)

    return data


# Stress Test 2: Two or more clients make the possible requests randomly.
def _stress_test_2_worker(user_id, n_requests, out_queue):
    db = get_db()

    data = {"n_requests": 0, "n_errors": 0}
    request_times = []

    async def attempt():
        idx = random.randint(0, 3)
        start_time = time.perf_counter()
        try:
            match idx:
                case 0:
                    house_id = uuid.uuid4()
                    await db.make_rental(
                        rental_id=uuid.uuid4(),
                        user_id=user_id,
                        house_id=house_id,
                        data_object={"some": "data"},
                    )
                case 1:
                    house_id = uuid.uuid4()
                    db.get_current_lock(house_id)
                case 2:
                    rental_id = uuid.uuid4()
                    db.get_rental(rental_id)
                case 3:
                    rental_id = uuid.uuid4()
                    house_id = uuid.uuid4()
                    await db.cancel_rental(
                        user_id=user_id,
                        house_id=house_id,
                        rental_id=rental_id,
                    )

            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            data["n_requests"] += 1
        except Exception as e:
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            data["n_requests"] += 1
            data["n_errors"] += 1
            print(f"Error in stress_test_2 worker for user {user_id}: {e}")

    async def run_all():
        sem = asyncio.Semaphore(200)

        async def wrapped(_):
            async with sem:
                await attempt()

        tasks = [wrapped(i) for i in range(n_requests)]
        await asyncio.gather(*tasks)

    try:
        asyncio.run(run_all())
    except Exception as e:
        print(f"Unexpected error in stress_test_2 worker for user {user_id}: {e}")

    out_queue.put((str(user_id), data, request_times))


def stress_test_2():
    # spawn one process per user and split requests between them
    user_ids = [uuid.uuid4(), uuid.uuid4()]

    requests_per_user = 2500

    result_queue = multiprocessing.Queue()
    processes = []
    for i, user_id in enumerate(user_ids):
        p = multiprocessing.Process(
            target=_stress_test_2_worker,
            args=(user_id, requests_per_user, result_queue),
        )
        p.start()
        processes.append(p)

    data = {"n_requests": 0, "n_errors": 0}
    request_times = []

    for _ in user_ids:
        user_key, user_data, req_times = result_queue.get()
        data["n_requests"] += user_data.get("n_requests", 0)
        data["n_errors"] += user_data.get("n_errors", 0)
        request_times.extend(req_times)

    for p in processes:
        p.join()

    data["request_stats"] = requests_stats(request_times)
    return data


# Stress Test 3: Immediate occupancy of all seats/reservations on 2 clients.
def _stress_test_3_worker(user_id, house_ids, out_queue):
    # each process gets its own DB connection(s)
    db = get_db()

    user_data = {
        "n_requests": 0,
        "n_successful_rents": 0,
        "n_failed_rents": 0,
        "n_errors": 0,
    }

    request_times = []
    # per-house successes (0 or 1) reported back to parent
    per_house_success = {house_id: 0 for house_id in house_ids}

    async def _attempt(house_id):
        await asyncio.sleep(random.uniform(0.001, 0.010))

        start_time = time.perf_counter()
        try:
            result = await db.make_rental(
                rental_id=uuid.uuid4(),
                user_id=user_id,
                house_id=house_id,
                data_object={"some": "data"},
            )
            end_time = time.perf_counter()

            request_times.append(end_time - start_time)
            user_data["n_requests"] += 1

            if not result:
                user_data["n_failed_rents"] += 1
            else:
                user_data["n_successful_rents"] += 1
                per_house_success[house_id] = 1
        except Exception as e:
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            user_data["n_requests"] += 1
            user_data["n_errors"] += 1
            print(f"Error in worker for user {user_id}: {e}")

    try:
        asyncio.run(run_stress_test(_attempt, items=house_ids, concurrency=200))
    except Exception as e:
        print(f"Unexpected error in worker for user {user_id}: {e}")

    # send results back to parent
    out_queue.put((str(user_id), user_data, request_times, per_house_success))


def stress_test_3(users=None):
    if users is None:
        users = [
            uuid.uuid4(),
            uuid.uuid4(),
        ]

    # We'll run one separate process per user. Each process will attempt to
    # rent every house from the same house list (with small jitter) and
    # then return per-process stats. The parent aggregates per-house
    # successes to detect double-rents.

    house_ids = [uuid.uuid4() for _ in range(3000)]

    # spawn processes
    result_queue = multiprocessing.Queue()
    processes = []
    for user_id in users:
        p = multiprocessing.Process(
            target=_stress_test_3_worker, args=(user_id, house_ids, result_queue)
        )
        p.start()
        processes.append(p)

    # collect results
    data = {
        str(user_id): {
            "n_requests": 0,
            "n_successful_rents": 0,
            "n_failed_rents": 0,
            "n_errors": 0,
        }
        for user_id in users
    }

    all_request_times = []
    # initialize aggregate counts per house
    n_successes_per_house = {house_id: 0 for house_id in house_ids}

    for _ in users:
        user_key, user_data, req_times, per_house = result_queue.get()
        data[user_key] = user_data
        all_request_times.extend(req_times)

        for hid, val in per_house.items():
            if val:
                n_successes_per_house[hid] += 1

    # ensure all processes have finished
    for p in processes:
        p.join()

    # detect double rents
    double_rents = sum(1 for c in n_successes_per_house.values() if c >= 2)

    data["double_rents"] = double_rents
    data["request_stats"] = requests_stats(all_request_times)

    data["n_successes_per_house"] = {
        "0": sum(1 for count in n_successes_per_house.values() if count == 0),
        "1": sum(1 for count in n_successes_per_house.values() if count == 1),
        "2": sum(1 for count in n_successes_per_house.values() if count >= 2),
    }

    return data


# Stress Test 4: Constant cancellations and seat occupancy.
def stress_test_4():
    house_ids = [uuid.uuid4() for _ in range(50)]
    db_connections = {}

    def get_db_for_user(uid):
        if uid not in db_connections:
            db_connections[uid] = get_db()
        return db_connections[uid]

    # 2 users try to rent a random house for ~100 ms.
    # The renting check algorithm is as follows:
    # - Rent the house
    # - If doesn't work - try another house
    # - Check that WE are renting the house
    #   (INCONSISTENCY if not)
    # - Wait for ~100 ms
    # - Check that WE are still renting the house (get rental)
    #   (INCONSISTENCY if not)
    # - Cancel the rental

    n_rentals_per_user = {}
    n_inconsistencies = 0
    n_errors = 0
    rent_req_times = []
    select_req_times = []
    cancel_req_times = []

    async def rental_test(user_id):
        nonlocal n_inconsistencies, n_errors
        db = get_db_for_user(user_id)

        rented_house = None
        rental_id = None

        for _ in range(10):  # try 10 times to rent a house
            house_id = random.choice(house_ids)

            start_time = time.perf_counter()
            try:
                result = await db.make_rental(
                    rental_id=uuid.uuid4(),
                    user_id=user_id,
                    house_id=house_id,
                    data_object={"some": "data"},
                )
                end_time = time.perf_counter()
                rent_req_times.append(end_time - start_time)

                if result:
                    rented_house = house_id
                    rental_id = uuid.uuid4()  # In direct mode, we need to track this
                    break
            except Exception as e:
                end_time = time.perf_counter()
                rent_req_times.append(end_time - start_time)
                n_errors += 1
                print(f"Error in make_rental: {e}")

            # don't be THAT annoying
            await asyncio.sleep(0.1)

        if not rented_house:
            # OK, we'll try later.
            return

        n_rentals_per_user[str(user_id)] = n_rentals_per_user.get(str(user_id), 0) + 1

        def check_renting(error_msg):
            nonlocal n_inconsistencies, n_errors

            start_time = time.perf_counter()
            try:
                lock_holder = db.get_current_lock(rented_house)
                end_time = time.perf_counter()
                select_req_times.append(end_time - start_time)

                if lock_holder != user_id:
                    print(
                        f"[RID={rental_id}] Inconsistency: {error_msg} (Expected user_id: {user_id}, Actual user_id: {lock_holder})"
                    )
                    n_inconsistencies += 1
            except Exception as e:
                end_time = time.perf_counter()
                select_req_times.append(end_time - start_time)
                n_errors += 1
                print(f"Error in get_current_lock: {e}")

        # Check that we are renting the house
        check_renting(
            "We rented the house but someone else is renting it immediately after!"
        )

        # Simulate holding the rental for ~100 ms
        await asyncio.sleep(0.1)

        # Check that we are still renting the house
        check_renting(
            "We rented the house but someone else is renting it after 100 ms!"
        )

        # Cancel the rental
        if rental_id:
            start_time = time.perf_counter()
            try:
                await db.cancel_rental(
                    user_id=user_id,
                    house_id=rented_house,
                    rental_id=rental_id,
                )
                end_time = time.perf_counter()
                cancel_req_times.append(end_time - start_time)
            except Exception as e:
                end_time = time.perf_counter()
                cancel_req_times.append(end_time - start_time)
                n_errors += 1
                print(
                    f"[RID={rental_id}] Error: We rented the house but couldn't cancel it! (Error: {e})"
                )

    users = [uuid.uuid4() for _ in range(2)]

    async def test(_idx):
        # try random user
        user_id = random.choice(users)
        try:
            await rental_test(user_id)
        except Exception:
            nonlocal n_errors
            n_errors += 1
            print(f"Error in rental_test for user {user_id}")
            import traceback

            traceback.print_exc()

    asyncio.run(run_stress_test(test, n_requests=500))

    return {
        "n_rentals_per_user": n_rentals_per_user,
        "n_inconsistencies": n_inconsistencies,
        "n_errors": n_errors,
        "rent_request_stats": requests_stats(rent_req_times),
        "select_request_stats": requests_stats(select_req_times),
        "cancel_request_stats": requests_stats(cancel_req_times),
    }


# Stress Test 5: Make large group cancellation of many reservations
def stress_test_5():
    # random houses
    houses = [uuid.uuid4() for _ in range(5000)]
    db = get_db()

    # rent them all (in parallel)
    async def rent_house(house_id):
        user_id = uuid.uuid4()
        try:
            result = await db.make_rental(
                rental_id=uuid.uuid4(),
                user_id=user_id,
                house_id=house_id,
                data_object={"some": "data"},
            )
            if not result:
                print(f"Failed to rent house {house_id}")
                return None
            return user_id, house_id
        except Exception as e:
            print(f"Failed to rent house {house_id}: {e}")
            return None

    async def rent_houses():
        tasks = [rent_house(house_id) for house_id in houses]
        return await asyncio.gather(*tasks)

    rentals = asyncio.run(rent_houses())

    request_times = []

    # cancel them all at once (only this one is timed)
    async def cancel_rental_timed(user_id, house_id):
        start_time = time.perf_counter()
        try:
            await db.cancel_rental(
                user_id=user_id,
                house_id=house_id,
                rental_id=uuid.uuid4(),
            )
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            return True
        except Exception as e:
            end_time = time.perf_counter()
            request_times.append(end_time - start_time)
            print(f"Error canceling rental: {e}")
            return False

    async def cancel_all():
        tasks = []
        for rental in rentals:
            if rental is not None:
                user_id, house_id = rental
                tasks.append(cancel_rental_timed(user_id, house_id))
        return await asyncio.gather(*tasks)

    start_time = time.perf_counter()
    cancel_results = asyncio.run(cancel_all())
    end_time = time.perf_counter()

    n_successful_cancels = sum(1 for result in cancel_results if result)
    n_failed_cancels = len(cancel_results) - n_successful_cancels

    return {
        "n_successful_cancels": n_successful_cancels,
        "n_failed_cancels": n_failed_cancels,
        "time_taken": end_time - start_time,
        "cancel_request_stats": requests_stats(request_times),
    }


def stress_test_3_distribution_test():
    users = [uuid.uuid4() for _ in range(2)]

    users_successes_samples = {user: list() for user in users}

    n_runs = 10
    for i in range(n_runs):
        print(f"Run {i + 1}/{n_runs}")
        result = stress_test_3(users=users)
        print(result)

        for user in users:
            users_successes_samples[user].append(
                result[str(user)]["n_successful_rents"]
            )

    # plot per-user histograms of successful rents
    import matplotlib.pyplot as plt
    import numpy as np

    # violinplot (SINGLE FIGURE/AX)
    plt.figure(figsize=(10, 6))
    plt.violinplot(
        [users_successes_samples[user] for user in users],
        showmeans=True,
        showmedians=True,
    )

    # raw samples
    plt.scatter(
        np.repeat(
            [1, 2],
            [
                len(users_successes_samples[users[0]]),
                len(users_successes_samples[users[1]]),
            ],
        ),
        users_successes_samples[users[0]] + users_successes_samples[users[1]],
        alpha=0.5,
    )

    plt.xticks([1, 2], [f"User {i + 1}" for i in range(len(users))])
    plt.ylabel("Number of successful rents")
    plt.title("Distribution of successful rents per user")
    plt.grid()
    plt.show()


if __name__ == "__main__":
    stress_tests = [
        stress_test_1_rent_separate_homes,
        stress_test_1_rent_same_home,
        stress_test_2,
        stress_test_3,
        stress_test_4,
        stress_test_5,
        stress_test_3_distribution_test,
    ]

    cmd_stress_test = sys.argv[1] if len(sys.argv) > 1 else None

    for test in stress_tests:
        if cmd_stress_test and test.__name__ != cmd_stress_test:
            continue

        print("-" * 10)
        print(f"Running {test.__name__}...")

        # truncate all before every test
        db = get_db()
        db.truncate_all()

        start_time = time.time()
        result = test()
        end_time = time.time()
        print(f"Result: {result}")
        print(f"Time taken: {end_time - start_time:.2f} seconds")
