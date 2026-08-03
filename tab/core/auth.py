from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .helpers import get_or_create_user, has_organization_email_domain
from .models import OIDCIdentity, Organization


class AuthentikOIDCBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims: dict[str, object]) -> bool:
        email = claims.get("email")
        return (
            super().verify_claims(claims)
            and isinstance(email, str)
            and claims.get("email_verified") is True
            and isinstance(claims.get("sub"), str)
            and bool(claims["sub"])
            and has_organization_email_domain(email)
        )

    def filter_users_by_claims(self, claims: dict[str, object]) -> QuerySet[User]:
        subject = claims.get("sub")
        if isinstance(subject, str):
            try:
                identity = OIDCIdentity.objects.get(
                    issuer=settings.OIDC_OP_ISSUER,
                    subject=subject,
                )
            except OIDCIdentity.DoesNotExist:
                pass
            else:
                return User.objects.filter(pk=identity.user_id)
        return super().filter_users_by_claims(claims)

    def create_user(self, claims: dict[str, object]) -> User:
        email = claims.get("email")
        if not isinstance(email, str) or not self.verify_claims(claims):
            raise SuspiciousOperation("OIDC email claim is not authorized")
        with transaction.atomic():
            domain = email.rpartition("@")[2]
            organization = (
                Organization.objects.select_for_update()
                .filter(email_domain__iexact=domain)
                .order_by("pk")
                .first()
            )
            if organization is None:
                raise SuspiciousOperation("OIDC email claim is not authorized")
            user = get_or_create_user(email)
            self._bind_identity(user, claims)
        return user

    def update_user(self, user: User, claims: dict[str, object]) -> User:
        self._bind_identity(user, claims)

        email = claims.get("email")
        if isinstance(email, str) and user.email.casefold() != email.casefold():
            if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
                raise SuspiciousOperation("OIDC email belongs to another user")
            user.email = email.lower()
            user.save(update_fields=["email"])
        return user

    @staticmethod
    def _bind_identity(user: User, claims: dict[str, object]) -> None:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise SuspiciousOperation("OIDC subject claim is missing")
        try:
            identity, _ = OIDCIdentity.objects.get_or_create(
                issuer=settings.OIDC_OP_ISSUER,
                subject=subject,
                defaults={"user": user},
            )
        except IntegrityError as error:
            raise SuspiciousOperation(
                "OIDC user is already bound to another identity"
            ) from error
        if identity.user_id != user.id:
            raise SuspiciousOperation("OIDC identity belongs to another user")

    def get_userinfo(
        self,
        access_token: str,
        id_token: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        user_info = super().get_userinfo(access_token, id_token, payload)
        if not isinstance(user_info, dict):
            raise SuspiciousOperation("OIDC UserInfo response is invalid")
        self.verify_userinfo_subject(payload, user_info)
        return user_info

    @staticmethod
    def verify_userinfo_subject(
        id_token_claims: dict[str, object], user_info: dict[str, object]
    ) -> None:
        id_token_subject = id_token_claims.get("sub")
        user_info_subject = user_info.get("sub")
        if (
            not isinstance(id_token_subject, str)
            or not id_token_subject
            or id_token_subject != user_info_subject
        ):
            raise SuspiciousOperation("OIDC UserInfo subject does not match ID token")

    def get_user(self, user_id: int) -> User | None:
        user = super().get_user(user_id)
        if user is None or not self.user_can_authenticate(user):
            return None
        return user

    def verify_token(self, token: str, **kwargs: object) -> dict[str, object]:
        claims = super().verify_token(token, **kwargs)
        self.verify_identity_token_claims(claims)
        return claims

    @staticmethod
    def verify_identity_token_claims(claims: dict[str, object]) -> None:
        if claims.get("iss") != settings.OIDC_OP_ISSUER:
            raise SuspiciousOperation("OIDC token has an invalid issuer")

        audience = claims.get("aud")
        audience_matches = audience == settings.OIDC_RP_CLIENT_ID or (
            isinstance(audience, list) and settings.OIDC_RP_CLIENT_ID in audience
        )
        if not audience_matches:
            raise SuspiciousOperation("OIDC token has an invalid audience")

        authorized_party = claims.get("azp")
        if (
            authorized_party is not None
            and authorized_party != settings.OIDC_RP_CLIENT_ID
        ):
            raise SuspiciousOperation("OIDC token has an invalid authorized party")
        if (
            isinstance(audience, list)
            and len(audience) > 1
            and authorized_party is None
        ):
            raise SuspiciousOperation("OIDC token has an invalid authorized party")
