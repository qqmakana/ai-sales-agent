from locust import HttpUser, task, between


class BasicLoadUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def load_home(self):
        self.client.get("/")

    @task(2)
    def load_login(self):
        self.client.get("/login")

    @task(1)
    def load_signup(self):
        self.client.get("/signup")
