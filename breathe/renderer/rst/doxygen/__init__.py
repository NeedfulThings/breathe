
from .base import Renderer, RenderContext
from . import index as indexrenderer
from . import compound as compoundrenderer

from docutils import nodes
import textwrap

class RstContentCreator(object):

    def __init__(self, list_type, dedent):

        self.list_type = list_type
        self.dedent = dedent

    def __call__(self, text):

        # Remove the first line which is "embed:rst[:leading-asterisk]"
        text = "\n".join(text.split(u"\n")[1:])

        # Remove starting whitespace
        text = self.dedent(text)

        # Inspired by autodoc.py in Sphinx
        result = self.list_type()
        for line in text.split("\n"):
            result.append(line, "<breathe>")

        return result

class UnicodeRenderer(Renderer):

    def render(self):

        # Skip any nodes that are pure whitespace
        # Probably need a better way to do this as currently we're only doing
        # it skip whitespace between higher-level nodes, but this will also
        # skip any pure whitespace entries in actual content nodes
        #
        # We counter that second issue slightly by allowing through single white spaces
        #
        if self.data_object.strip():
            return [self.node_factory.Text(self.data_object)]
        elif self.data_object == unicode(" "):
            return [self.node_factory.Text(self.data_object)]
        else:
            return []

class NullRenderer(Renderer):

    def __init__(self):
        pass

    def render(self):
        return []


class DoxygenToRstRendererFactory(object):

    def __init__(
            self,
            node_type,
            renderers,
            renderer_factory_creator,
            node_factory,
            project_info,
            state,
            document,
            rst_content_creator,
            filter_,
            target_handler,
            domain_directive_factory
            ):

        self.node_type = node_type
        self.node_factory = node_factory
        self.project_info = project_info
        self.renderers = renderers
        self.renderer_factory_creator = renderer_factory_creator
        self.state = state
        self.document = document
        self.rst_content_creator = rst_content_creator
        self.filter_ = filter_
        self.target_handler = target_handler
        self.domain_directive_factory = domain_directive_factory

    def create_renderer(
            self,
            context
            ):

        parent_data_object = context.node_stack[1]
        data_object = context.node_stack[0]

        if not self.filter_.allow(context.node_stack):
            return NullRenderer()

        child_renderer_factory = self.renderer_factory_creator.create_child_factory(
                self.project_info,
                data_object,
                self
                )

        try:
            node_type = data_object.node_type
        except AttributeError as e:

            # Horrible hack to silence errors on filtering unicode objects
            # until we fix the parsing
            if type(data_object) == unicode:
                node_type = "unicode"
            else:
                raise e

        Renderer = self.renderers[node_type]

        common_args = [
                self.project_info,
                context,
                child_renderer_factory,
                self.node_factory,
                self.state,
                self.document,
                self.target_handler,
                self.domain_directive_factory
                ]

        if node_type == "docmarkup":

            creator = self.node_factory.inline
            if data_object.type_ == "emphasis":
                creator = self.node_factory.emphasis
            elif data_object.type_ == "computeroutput":
                creator = self.node_factory.literal
            elif data_object.type_ == "bold":
                creator = self.node_factory.strong
            elif data_object.type_ == "superscript":
                creator = self.node_factory.superscript
            elif data_object.type_ == "subscript":
                creator = self.node_factory.subscript
            elif data_object.type_ == "center":
                print("Warning: does not currently handle 'center' text display")
            elif data_object.type_ == "small":
                print("Warning: does not currently handle 'small' text display")

            return Renderer(
                    creator,
                    *common_args
                    )

        if node_type == "verbatim":

            return Renderer(
                    self.rst_content_creator,
                    *common_args
                    )

        if node_type == "compound":

            kind = data_object.kind
            if kind in ["file", "dir", "page", "example", "group"]:
                return Renderer(indexrenderer.FileRenderer, *common_args)

            class_ = indexrenderer.CompoundTypeSubRenderer

            # For compound node types Renderer is CreateCompoundTypeSubRenderer
            # as defined below. This could be cleaner
            return Renderer(
                    class_,
                    *common_args
                    )

        if node_type == "memberdef":

            if data_object.kind in ("function", "slot"):
                Renderer = compoundrenderer.FuncMemberDefTypeSubRenderer
            elif data_object.kind == "enum":
                Renderer = compoundrenderer.EnumMemberDefTypeSubRenderer
            elif data_object.kind == "typedef":
                Renderer = compoundrenderer.TypedefMemberDefTypeSubRenderer
            elif data_object.kind == "variable":
                Renderer = compoundrenderer.VariableMemberDefTypeSubRenderer
            elif data_object.kind == "define":
                Renderer = compoundrenderer.DefineMemberDefTypeSubRenderer

        if node_type == "param":
            return Renderer(
                    parent_data_object.node_type != "templateparamlist", 
                    *common_args
                    )

        if node_type == "docsimplesect":
            if data_object.kind == "par":
                Renderer = compoundrenderer.ParDocSimpleSectTypeSubRenderer

        return Renderer(
                *common_args
                )

class CreateCompoundTypeSubRenderer(object):

    def __init__(self, parser_factory):

        self.parser_factory = parser_factory

    def __call__(self, class_, project_info, *args):

        compound_parser = self.parser_factory.create_compound_parser(project_info)
        return class_(compound_parser, project_info, *args)


class CreateRefTypeSubRenderer(object):

    def __init__(self, parser_factory):

        self.parser_factory = parser_factory

    def __call__(self, project_info, *args):

        compound_parser = self.parser_factory.create_compound_parser(project_info)
        return compoundrenderer.RefTypeSubRenderer(compound_parser, project_info, *args)


class DoxygenToRstRendererFactoryCreator(object):

    def __init__(
            self,
            node_factory,
            parser_factory,
            domain_directive_factory,
            rst_content_creator,
            project_info
            ):

        self.node_factory = node_factory
        self.parser_factory = parser_factory
        self.domain_directive_factory = domain_directive_factory
        self.rst_content_creator = rst_content_creator
        self.project_info = project_info

    def create_factory(self, node_stack, state, document, filter_, target_handler):

        data_object = node_stack[0]

        renderers = {
            "doxygen" : indexrenderer.DoxygenTypeSubRenderer,
            "compound" : CreateCompoundTypeSubRenderer(self.parser_factory),
            "doxygendef" : compoundrenderer.DoxygenTypeSubRenderer,
            "compounddef" : compoundrenderer.CompoundDefTypeSubRenderer,
            "sectiondef" : compoundrenderer.SectionDefTypeSubRenderer,
            "memberdef" : compoundrenderer.MemberDefTypeSubRenderer,
            "enumvalue" : compoundrenderer.EnumvalueTypeSubRenderer,
            "linkedtext" : compoundrenderer.LinkedTextTypeSubRenderer,
            "description" : compoundrenderer.DescriptionTypeSubRenderer,
            "param" : compoundrenderer.ParamTypeSubRenderer,
            "docreftext" : compoundrenderer.DocRefTextTypeSubRenderer,
            "docheading" : compoundrenderer.DocHeadingTypeSubRenderer,
            "docpara" : compoundrenderer.DocParaTypeSubRenderer,
            "docmarkup" : compoundrenderer.DocMarkupTypeSubRenderer,
            "docparamlist" : compoundrenderer.DocParamListTypeSubRenderer,
            "docparamlistitem" : compoundrenderer.DocParamListItemSubRenderer,
            "docparamnamelist" : compoundrenderer.DocParamNameListSubRenderer,
            "docparamname" : compoundrenderer.DocParamNameSubRenderer,
            "docsect1" : compoundrenderer.DocSect1TypeSubRenderer,
            "docsimplesect" : compoundrenderer.DocSimpleSectTypeSubRenderer,
            "doctitle" : compoundrenderer.DocTitleTypeSubRenderer,
            "docformula" : compoundrenderer.DocForumlaTypeSubRenderer,
            "docimage" : compoundrenderer.DocImageTypeSubRenderer,
            "docurllink" : compoundrenderer.DocURLLinkSubRenderer,
            "listing" : compoundrenderer.ListingTypeSubRenderer,
            "codeline" : compoundrenderer.CodeLineTypeSubRenderer,
            "highlight" : compoundrenderer.HighlightTypeSubRenderer,
            "templateparamlist" : compoundrenderer.TemplateParamListRenderer,
            "inc" : compoundrenderer.IncTypeSubRenderer,
            "ref" : CreateRefTypeSubRenderer(self.parser_factory),
            "verbatim" : compoundrenderer.VerbatimTypeSubRenderer,
            "mixedcontainer" : compoundrenderer.MixedContainerRenderer,
            "unicode" : UnicodeRenderer,
            "doclist": compoundrenderer.DocListTypeSubRenderer,
            "doclistitem": compoundrenderer.DocListItemTypeSubRenderer,
            }

        try:
            node_type = data_object.node_type
        except AttributeError as e:

            # Horrible hack to silence errors on filtering unicode objects
            # until we fix the parsing
            if type(data_object) == unicode:
                node_type = "unicode"
            else:
                raise e

        return DoxygenToRstRendererFactory(
                "root",
                renderers,
                self,
                self.node_factory,
                self.project_info,
                state,
                document,
                self.rst_content_creator,
                filter_,
                target_handler,
                self.domain_directive_factory
                )

    def create_child_factory( self, project_info, data_object, parent_renderer_factory ):

        try:
            node_type = data_object.node_type
        except AttributeError as e:

            # Horrible hack to silence errors on filtering unicode objects
            # until we fix the parsing
            if type(data_object) == unicode:
                node_type = "unicode"
            else:
                raise e

        return DoxygenToRstRendererFactory(
                    node_type,
                    parent_renderer_factory.renderers,
                    self,
                    self.node_factory,
                    parent_renderer_factory.project_info,
                    parent_renderer_factory.state,
                    parent_renderer_factory.document,
                    self.rst_content_creator,
                    parent_renderer_factory.filter_,
                    parent_renderer_factory.target_handler,
                    parent_renderer_factory.domain_directive_factory
                    )


# FactoryFactoryFactory. Ridiculous but necessary.
class DoxygenToRstRendererFactoryCreatorConstructor(object):

    def __init__(
            self,
            node_factory,
            parser_factory,
            domain_directive_factory,
            rst_content_creator
            ):

        self.node_factory = node_factory
        self.parser_factory = parser_factory
        self.domain_directive_factory = domain_directive_factory
        self.rst_content_creator = rst_content_creator

    def create_factory_creator(self, project_info, document, options, target_handler):

        return DoxygenToRstRendererFactoryCreator(
                self.node_factory,
                self.parser_factory,
                self.domain_directive_factory,
                self.rst_content_creator,
                project_info,
                )


def format_parser_error(name, error, filename, state, lineno, do_unicode_warning):

    warning = '%s: Unable to parse xml file "%s". ' % (name, filename)
    explanation = 'Reported error: %s. ' % error

    unicode_explanation_text = ""
    unicode_explanation = []
    if do_unicode_warning:
        unicode_explanation_text = textwrap.dedent("""
        Parsing errors are often due to unicode errors associated with the encoding of the original
        source files. Doxygen propagates invalid characters from the input source files to the
        output xml.""").strip().replace("\n", " ")
        unicode_explanation = [nodes.paragraph("", "", nodes.Text(unicode_explanation_text))]

    return [nodes.warning("",
                nodes.paragraph("", "", nodes.Text(warning)),
                nodes.paragraph("", "", nodes.Text(explanation)),
                *unicode_explanation
                ),
            state.document.reporter.warning(warning + explanation + unicode_explanation_text, line=lineno)
            ]
