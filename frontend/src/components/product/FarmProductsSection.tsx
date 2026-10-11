import { useEffect, useState } from 'react'
import { describeApiError } from '../../api/errors.ts'
import {
  createProduct,
  fetchMyProducts,
  updateProduct,
  updateProductInventory,
  type Product,
  type ProductDetails,
} from '../../api/products.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName } from '../buttonStyles.ts'
import ProductForm from './ProductForm.tsx'
import ProductListItem from './ProductListItem.tsx'

type ProductsLoadState =
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; products: Product[] }

type EditorState =
  | { mode: 'closed' }
  | { mode: 'adding' }
  | { mode: 'editing'; product: Product }

function toDetails(product: Product): ProductDetails {
  return {
    name: product.name,
    category: product.category,
    description: product.description,
    price: product.price,
    unit: product.unit,
    harvest_date: product.harvest_date,
    available_from: product.available_from,
    available_until: product.available_until,
    organic: product.organic,
    active: product.active,
  }
}

/** The signed-in farmer's product list, with adding, editing, stock and visibility controls. */
export default function FarmProductsSection() {
  const accessToken = useAccessToken()
  const [productsState, setProductsState] = useState<ProductsLoadState>({ status: 'loading' })
  const [editor, setEditor] = useState<EditorState>({ mode: 'closed' })
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true
    fetchMyProducts(accessToken)
      .then((products) => {
        if (isCurrent) {
          setProductsState({ status: 'loaded', products })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setProductsState({ status: 'failed', message: describeApiError(error) })
        }
      })
    return () => {
      isCurrent = false
    }
  }, [accessToken])

  function showSavedProduct(savedProduct: Product, message: string) {
    setProductsState((current) => {
      if (current.status !== 'loaded') {
        return current
      }
      const isExisting = current.products.some((product) => product.id === savedProduct.id)
      const products = isExisting
        ? current.products.map((product) =>
            product.id === savedProduct.id ? savedProduct : product,
          )
        : [savedProduct, ...current.products]
      return { status: 'loaded', products }
    })
    setEditor({ mode: 'closed' })
    setNotice(message)
  }

  async function handleAdd(details: ProductDetails, openingStock: number) {
    const product = await createProduct(accessToken, {
      ...details,
      quantity_available: openingStock,
    })
    showSavedProduct(product, `${product.name} has been added.`)
  }

  async function handleEdit(productId: number, details: ProductDetails) {
    const product = await updateProduct(accessToken, productId, details)
    showSavedProduct(product, `${product.name} has been saved.`)
  }

  async function handleUpdateStock(product: Product, quantityAvailable: number) {
    const updatedProduct = await updateProductInventory(accessToken, product.id, quantityAvailable)
    showSavedProduct(updatedProduct, `Stock for ${updatedProduct.name} has been updated.`)
  }

  async function handleSetActive(product: Product, active: boolean) {
    const updatedProduct = await updateProduct(accessToken, product.id, {
      ...toDetails(product),
      active,
    })
    showSavedProduct(
      updatedProduct,
      active
        ? `${updatedProduct.name} is visible to customers again.`
        : `${updatedProduct.name} is now hidden from customers.`,
    )
  }

  function openEditor(nextEditor: EditorState) {
    setNotice(null)
    setEditor(nextEditor)
  }

  return (
    <section aria-labelledby="products-heading" className="pt-6">
      <div className="flex items-center justify-between gap-4">
        <h2 id="products-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Products
        </h2>
        {productsState.status === 'loaded' && editor.mode === 'closed' && (
          <button
            type="button"
            onClick={() => openEditor({ mode: 'adding' })}
            className={primaryButtonClassName}
          >
            Add Product
          </button>
        )}
      </div>

      <div className="mt-4 space-y-4">
        {notice && (
          <p
            role="status"
            className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
          >
            {notice}
          </p>
        )}

        {productsState.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading your products…
          </p>
        )}

        {productsState.status === 'failed' && (
          <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Your products could not be loaded. {productsState.message}
          </p>
        )}

        {editor.mode === 'adding' && (
          <ProductForm
            initialProduct={null}
            onSubmit={handleAdd}
            onCancel={() => setEditor({ mode: 'closed' })}
          />
        )}

        {editor.mode === 'editing' && (
          <ProductForm
            key={editor.product.id}
            initialProduct={editor.product}
            onSubmit={(details) => handleEdit(editor.product.id, details)}
            onCancel={() => setEditor({ mode: 'closed' })}
          />
        )}

        {productsState.status === 'loaded' &&
          productsState.products.length === 0 &&
          editor.mode === 'closed' && (
            <div className="rounded-xl border border-dashed border-stone-300 bg-white p-8 text-center">
              <p className="font-semibold text-stone-900">You have not listed any products yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
                Add what you have to sell so customers searching nearby can find it.
              </p>
            </div>
          )}

        {productsState.status === 'loaded' && productsState.products.length > 0 && (
          <ul className="space-y-3">
            {productsState.products.map((product) => (
              <ProductListItem
                // Remounting when stock changes resets the stock input to the saved value.
                key={`${product.id}-${product.quantity_available}`}
                product={product}
                onEdit={() => openEditor({ mode: 'editing', product })}
                onUpdateStock={(quantityAvailable) => handleUpdateStock(product, quantityAvailable)}
                onSetActive={(active) => handleSetActive(product, active)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
