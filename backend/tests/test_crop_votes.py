import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.crop_poll import CropPoll, CropPollOption, CropPollStatus, CropVote
from app.models.farm import Farm
from app.models.user import User, UserRole
from app.schemas.crop_poll import CropVoteCreate
from app.services.crop_polls import AlreadyVotedError, cast_vote
from tests.concurrency import SessionFactory, WaitForStart, run_together
from tests.helpers import (
    auth_headers,
    create_crop_poll,
    create_farmer_with_farm,
    create_user,
    create_vote,
)

CROP_VOTES_URL = "/api/crop-votes"
MY_CROP_VOTES_URL = "/api/crop-votes/mine"


def count_votes(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(CropVote)) or 0


def vote(client: TestClient, customer: User, option: CropPollOption):
    return client.post(
        CROP_VOTES_URL,
        json={"poll_id": option.poll_id, "option_id": option.id},
        headers=auth_headers(customer),
    )


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com", farm_name="Green Acres")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


@pytest.fixture
def poll(db_session: Session, farm: Farm) -> CropPoll:
    return create_crop_poll(db_session, farm)


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


@pytest.fixture
def other_customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="other-customer@example.com")


class TestCastVote:
    def test_customer_votes_for_an_option(
        self, client: TestClient, db_session: Session, customer: User, poll: CropPoll
    ) -> None:
        okra = poll.options[0]

        response = vote(client, customer, okra)

        assert response.status_code == 201
        body = response.json()
        assert body["poll_id"] == poll.id
        assert body["option_id"] == okra.id
        assert body["poll"]["total_votes"] == 1
        assert [option["votes"] for option in body["poll"]["options"]] == [1, 0, 0]

        stored_vote = db_session.scalar(select(CropVote))
        assert stored_vote is not None
        assert stored_vote.customer_id == customer.id

    def test_customer_can_vote_only_once_in_a_poll(
        self, client: TestClient, db_session: Session, customer: User, poll: CropPoll
    ) -> None:
        okra, corn, _greens = poll.options

        first = vote(client, customer, okra)
        same_option_again = vote(client, customer, okra)
        different_option = vote(client, customer, corn)

        assert first.status_code == 201
        assert same_option_again.status_code == 409
        assert different_option.status_code == 409
        assert different_option.json() == {"detail": "You have already voted in this crop poll"}
        assert count_votes(db_session) == 1

    def test_each_customer_gets_their_own_vote(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        poll: CropPoll,
    ) -> None:
        okra, corn, _greens = poll.options

        vote(client, customer, okra)
        response = vote(client, other_customer, corn)

        assert response.status_code == 201
        assert response.json()["poll"]["total_votes"] == 2
        assert [option["votes"] for option in response.json()["poll"]["options"]] == [1, 1, 0]

    def test_customer_can_vote_in_several_polls(
        self, client: TestClient, db_session: Session, customer: User, poll: CropPoll, farm: Farm
    ) -> None:
        second_poll = create_crop_poll(db_session, farm, options=("Kale", "Leeks"))

        assert vote(client, customer, poll.options[0]).status_code == 201
        assert vote(client, customer, second_poll.options[0]).status_code == 201

    def test_option_from_another_poll_is_rejected(
        self, client: TestClient, db_session: Session, customer: User, poll: CropPoll, farm: Farm
    ) -> None:
        other_poll = create_crop_poll(db_session, farm, options=("Kale", "Leeks"))

        response = client.post(
            CROP_VOTES_URL,
            json={"poll_id": poll.id, "option_id": other_poll.options[0].id},
            headers=auth_headers(customer),
        )

        assert response.status_code == 422
        assert response.json() == {"detail": "That option is not part of this crop poll"}
        assert count_votes(db_session) == 0

    def test_closed_poll_takes_no_votes(
        self, client: TestClient, db_session: Session, customer: User, farm: Farm
    ) -> None:
        closed_poll = create_crop_poll(db_session, farm, status=CropPollStatus.CLOSED)

        response = vote(client, customer, closed_poll.options[0])

        assert response.status_code == 409
        assert response.json() == {"detail": "This crop poll is closed"}
        assert count_votes(db_session) == 0

    def test_unknown_poll_is_not_found(self, client: TestClient, customer: User) -> None:
        response = client.post(
            CROP_VOTES_URL,
            json={"poll_id": 999999, "option_id": 1},
            headers=auth_headers(customer),
        )

        assert response.status_code == 404

    def test_only_customers_can_vote(
        self, client: TestClient, db_session: Session, farmer: User, poll: CropPoll
    ) -> None:
        option = poll.options[0]

        assert vote(client, farmer, option).status_code == 403
        assert (
            client.post(
                CROP_VOTES_URL, json={"poll_id": poll.id, "option_id": option.id}
            ).status_code
            == 401
        )
        assert count_votes(db_session) == 0

    def test_customer_in_the_request_body_is_ignored(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        poll: CropPoll,
    ) -> None:
        option = poll.options[0]

        response = client.post(
            CROP_VOTES_URL,
            json={"poll_id": poll.id, "option_id": option.id, "customer_id": other_customer.id},
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        stored_vote = db_session.scalar(select(CropVote))
        assert stored_vote is not None
        assert stored_vote.customer_id == customer.id


class TestVoteConstraints:
    def test_database_rejects_a_second_vote_from_the_same_customer(
        self, db_session: Session, customer: User, poll: CropPoll
    ) -> None:
        create_vote(db_session, customer, poll.options[0])

        with pytest.raises(IntegrityError, match="uq_crop_votes_poll_id_customer_id"):
            create_vote(db_session, customer, poll.options[1])

    def test_database_rejects_a_vote_whose_option_belongs_to_another_poll(
        self, db_session: Session, customer: User, poll: CropPoll, farm: Farm
    ) -> None:
        other_poll = create_crop_poll(db_session, farm, options=("Kale", "Leeks"))
        db_session.add(
            CropVote(poll_id=poll.id, option_id=other_poll.options[0].id, customer_id=customer.id)
        )

        with pytest.raises(
            IntegrityError, match="fk_crop_votes_poll_id_option_id_crop_poll_options"
        ):
            db_session.commit()


class TestListMyVotes:
    def test_customer_sees_which_option_they_chose_in_each_poll(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        poll: CropPoll,
    ) -> None:
        create_vote(db_session, customer, poll.options[1])
        create_vote(db_session, other_customer, poll.options[0])

        response = client.get(MY_CROP_VOTES_URL, headers=auth_headers(customer))

        assert response.status_code == 200
        assert response.json() == [{"poll_id": poll.id, "option_id": poll.options[1].id}]

    def test_listing_is_for_customers_only(self, client: TestClient, farmer: User) -> None:
        assert client.get(MY_CROP_VOTES_URL, headers=auth_headers(farmer)).status_code == 403
        assert client.get(MY_CROP_VOTES_URL).status_code == 401


def test_one_customer_voting_twice_at_once_gets_one_vote(
    committing_session_factory: SessionFactory,
) -> None:
    """Two requests from the same customer race on separate connections."""
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        poll = create_crop_poll(setup, farm)
        poll_id, option_ids = poll.id, [option.id for option in poll.options]
        customer_id = create_user(setup, role=UserRole.CUSTOMER, email="customer@example.com").id

    def voting_for(option_id: int):
        def action(wait_for_start: WaitForStart) -> str:
            with committing_session_factory() as session:
                customer = session.get(User, customer_id)
                assert customer is not None
                details = CropVoteCreate(poll_id=poll_id, option_id=option_id)
                wait_for_start()
                try:
                    cast_vote(session, customer, details)
                except AlreadyVotedError:
                    return "refused"
                return "voted"

        return action

    outcomes = run_together([voting_for(option_ids[0]), voting_for(option_ids[1])])

    assert outcomes == ["refused", "voted"]
    with committing_session_factory() as check:
        assert check.scalar(select(func.count()).select_from(CropVote)) == 1
