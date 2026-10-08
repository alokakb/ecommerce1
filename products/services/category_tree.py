from unicodedata import category

from products.models import Category


class CategoryTreeService:

    @staticmethod
    def get_all_descendant_ids(category: Category) -> list[int]:

        descendant_ids = [category.id]

        for child in category.children.all():
            descendant_ids.extend(CategoryTreeService.get_all_descendant_ids(child))

        return descendant_ids