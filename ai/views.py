"""
ai.views
---------
Phase 4 item 21 (FAQ chatbot) lives here, in the shared ai app itself,
rather than in catalog/leads/wherever -- unlike every other Phase 4
feature, it isn't an AI layer bolted onto one specific app's existing
model/endpoint; it's a standalone public endpoint in its own right.

Phase 4 item 25 (AI-generated area/landing pages) is a management
command, not a view -- see apps/ai/management/commands/, since the
frontend is static HTML with no CMS behind it, so "generate a page"
means "generate copy a person pastes into a new HTML file", not
"create a live route."
"""

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.ai.client import AIUnavailableError, complete

from .serializers import FAQChatSerializer

# Kept as a plain constant, not pulled from the database, deliberately:
# this is marketing/support copy that changes rarely and should be
# reviewed by a person before it changes what the bot tells parents,
# not silently drift whenever someone edits an Area row for an
# unrelated reason. Update this text by hand when the facts change.
TUTORO_FACTS = """
Tutoro is a tutor-matching service operating in Hyderabad, India.
- Parents submit a request describing their child's class, subject(s),
  and preferred teaching mode; Tutoro's staff (with AI-assisted
  matching) suggest suitable tutors.
- Three teaching modes: HOME (tutor visits the student), ONLINE (video
  classes), and ACADEMY (referral to a partner coaching institute).
  Parents can also choose ANY to stay open to whichever is available.
- Tutors go through a verification process before being shown to
  parents; a "VERIFIED" badge means Tutoro has checked their
  qualifications.
- Tutoro currently covers several localities around Hyderabad
  (including areas like Gachibowli, Kondapur, Madhapur, Kukatpally,
  KPHB, Miyapur, and nearby areas) plus fully remote online tutoring
  anywhere.
- Tutoro collects a parent's consent before processing their data, in
  line with India's DPDP Act.
""".strip()


class FAQChatThrottle(AnonRateThrottle):
    scope = "faq_chat"


class FAQChatView(APIView):
    """
    POST /api/ai/faq/  body: {"question": "..."}
    Public, no auth required -- this is meant to sit on the marketing
    site for a visitor who hasn't signed up yet. Stateless: no
    conversation history is stored or sent, so answers can't drift
    based on earlier turns and there's no chat-log data to manage
    under DPDP for an anonymous visitor.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [FAQChatThrottle]

    def post(self, request):
        serializer = FAQChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]

        system = (
            "You are Tutoro's website FAQ assistant. Answer ONLY using the "
            "facts below. If the question asks something not covered here "
            "(exact pricing, specific tutor availability, account-specific "
            "questions, anything you're not told), say you don't have that "
            "information and suggest they contact Tutoro support or submit a "
            "request on the site -- never guess or invent a number, name, or "
            "policy detail. Keep answers to 2-4 short sentences, plain text, "
            "no markdown.\n\n" + TUTORO_FACTS
        )

        try:
            answer = complete(system, question, max_tokens=300)
        except AIUnavailableError:
            return Response(
                {"detail": "The FAQ assistant isn't available right now. Please contact Tutoro support directly."},
                status=503,
            )
        except Exception:
            return Response(
                {"detail": "Couldn't get an answer right now. Please try again shortly."},
                status=503,
            )

        return Response({"answer": answer.strip()})
