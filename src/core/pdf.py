import io
from typing import Any, Dict, List

from django.template.loader import render_to_string
from fpdf import FPDF

from core.mixins import ConversationMixin


def _paragraphize(text: str) -> List[str]:
    text_paragraphs = text.strip().split('\n')
    return [paragraph for paragraph in text_paragraphs if paragraph]


# TODO: ideally should be unit tested
# https://py-pdf.github.io/fpdf2/HTML.html#supported-html-features
def _build_conversation_html(
    conversation_title: str,
    message_dict_list: List[Dict[str, str]],
    reference_list_list: List[List[Dict[str, str]]],
) -> str:
    if len(message_dict_list) != len(reference_list_list):
        raise RuntimeError()

    messages_with_references: List[Dict[str, Any]] = []

    # pylint: disable=consider-using-enumerate
    for i in range(len(message_dict_list)):
        message_dict = message_dict_list[i]
        reference_list = reference_list_list[i]

        messages_with_references.append(
            {'role': 'Kasutaja', 'paragraphs': _paragraphize(message_dict['user'])}
        )
        messages_with_references.append(
            {
                'role': 'Vastus',
                'paragraphs': _paragraphize(message_dict['assistant']),
                'references': reference_list,
            }
        )

    context = {
        'conversation_title': conversation_title,
        'messages_with_references': messages_with_references,
    }
    return render_to_string(template_name='conversation.html', context=context)


def pdf_file_bytes_from_conversation(conversation: ConversationMixin) -> io.BytesIO:
    html = _build_conversation_html(
        conversation_title=conversation.title,
        message_dict_list=conversation.messages_for_pdf,
        reference_list_list=conversation.references_for_pdf,
    )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica')
    pdf.set_text_color(0, 0, 0)
    pdf.write_html(html)

    # You can uncomment this and run tests to look at the produced PDF
    # if conversation.references_for_pdf:
    #     pdf.output('messages.pdf')

    # Necessary for Djangos FileResponse class to return a
    # proper file towards the front-end.
    buffer = io.BytesIO(pdf.output())
    buffer.seek(0)

    return buffer
