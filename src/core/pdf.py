from typing import Dict, List

from fpdf import FPDF

from core.mixins import ConversationMixin


# TODO: ideally should be unit tested
# https://py-pdf.github.io/fpdf2/HTML.html#supported-html-features
def _build_conversation_html(
    conversation_title: str,
    message_dict_list: List[Dict[str, str]],
    reference_list_list: List[List[Dict[str, str]]],
) -> str:
    if len(message_dict_list) != len(reference_list_list):
        raise RuntimeError()

    roles_in_order = ['user', 'assistant']
    role_translation_map = {'user': 'Kasutaja', 'assistant': 'Vastus'}

    html_pieces = [f'<h1 style="color:black" >{conversation_title}</h1>']

    # pylint: disable=consider-using-enumerate
    for i in range(len(message_dict_list)):
        message_dict = message_dict_list[i]
        reference_list = reference_list_list[i]

        html_pieces.append('')

        for key in roles_in_order:
            html_pieces.append(f'<h2 style="color:black" >{role_translation_map[key]}:</h2>')

            content = message_dict[key]
            content_paragraphs = content.strip().split('\n')

            for content_paragraph in content_paragraphs:
                if not content_paragraph:
                    continue
                html_pieces.append(f'<p style="color:black" >{content_paragraph}</p>')

        if not reference_list:
            continue

        html_pieces.append('<h4 style="color:black" >Viited:</h4>')
        html_pieces.append('<ol style="color:black" >')

        for reference in reference_list:
            html_pieces.append(
                '<li>' f'{reference["title"]}, ' f'<a href="{reference["url"]}" >LINK</a>' '</li>'
            )

        html_pieces.append('</ol>')

    return '\n'.join(html_pieces)


def pdf_file_bytes_from_conversation(conversation: ConversationMixin) -> bytes:
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

    return pdf.output()
