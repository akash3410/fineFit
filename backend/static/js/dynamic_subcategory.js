let django = document.getElementById('id_category');
let subcategory = document.getElementById('id_subcategory');

if (django && subcategory) {
    function updateSubcategories() {
        let categoryId = django.value;
        if (!categoryId) {
            subcategory.innerHTML = '<option value="">---------</option>';
            return;
        }
        
        fetch(`/admin/catalog/api/subcategories/${categoryId}/`)
            .then(response => response.json())
            .then(data => {
                subcategory.innerHTML = '<option value="">---------</option>';
                data.subcategories.forEach(sc => {
                    let option = document.createElement('option');
                    option.value = sc.id;
                    option.textContent = sc.name;
                    subcategory.appendChild(option);
                });
            })
            .catch(error => {
                console.log('Error loading subcategories:', error);
            });
    }
    
    django.addEventListener('change', updateSubcategories);
    // Initial call
    updateSubcategories();
}
