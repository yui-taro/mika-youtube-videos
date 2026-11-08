# 質問：LWCの`reduceErrors`は、常に使うのが最適ですか？

## 回答

**いいえ。必要なときだけ使えば十分です。** `reduceErrors`は、エラーから**画面に表示する文章を取り出す**ための関数です。エラーを直したり、エラーの種類に応じて処理を分けたりする関数ではありません。

### 使うとき

ApexやUI APIなど、**返ってくるエラーの形が違っても、表示文言をまとめて取り出したいとき**に便利です。複数のメッセージも配列で受け取れます。

```js
// LWC RecipesのldsUtils.jsをプロジェクトに置いた場合
import { reduceErrors } from 'c/ldsUtils';

this.errorMessage = reduceErrors(error).join(' / ');
```

`reduceErrors`はSalesforceの組み込み関数ではなく、[LWC Recipesのサンプル実装](https://github.com/trailheadapps/lwc-recipes/blob/main/force-app/main/default/lwc/ldsUtils/ldsUtils.js)です。

**公式資料の該当箇所：** [LWC「Handle Errors in Lightning Data Service」](https://developer.salesforce.com/docs/platform/lwc/guide/data-error.html)の「The body of the error response depends on the API that returns it」に、APIごとにエラーの形が違うことと、`ldsUtils`の案内があります。

### 使わない例（3つ）

以下はコンポーネント内の短い抜粋です。`this.errorMessage`は画面表示用のプロパティを想定しています。

**1. Apexエラーの文章を1つだけ表示する**

```js
catch (error) {
    this.errorMessage = error?.body?.message || '保存できませんでした。';
}
```

呼び出しているApexのエラー形式が分かっていれば、直接取り出せます。**公式資料の該当箇所：** [Salesforce Developers Blog「Understanding the error body payload」](https://developer.salesforce.com/blogs/2020/08/error-handling-best-practices-for-lightning-web-components)の`body.message`の説明。

**2. エラーコードで分け、決まった文章を表示する**

```js
// getRecordなど、error.bodyが配列の場合
const code = error?.body?.[0]?.errorCode;
this.errorMessage = code === 'INSUFFICIENT_PRIVILEGES'
    ? '閲覧権限がありません。'
    : '読み込めませんでした。';
```

分岐には、文章に変換する前の`error`を使います。コードの場所と値は実際の応答で確認してください。**公式資料の該当箇所：** [LWCのエラー形式](https://developer.salesforce.com/docs/platform/lwc/guide/data-error.html)にUI API読み取り時の配列、[User Interface API Developer Guide「Error Message」](https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/api_ui.pdf)に`errorCode`と値の例があります。

**3. 送信前にフォームの入力を確認する**

```html
<lightning-input label="名前" required></lightning-input>
```

```js
const input = this.template.querySelector('lightning-input');
input.reportValidity();
if (!input.validity.valid) return;
```

これはSalesforceから返ったエラーを読む処理ではありません。**公式リファレンスの該当箇所：** [`lightning-input`の「Input Validation」](https://developer.salesforce.com/docs/platform/lightning-component-reference/guide/lightning-input.html?type=Develop)に、`required`、`reportValidity()`、`validity.valid`が説明されています。

**まとめ：表示文言を取り出すなら`reduceErrors`を検討。それ以外は、目的に合う処理を直接書きます。** 「常に使う」「この3例では使わない」と定めた公式ルールはありません。

---

# 質問：`AuraHandledException`にメッセージを2つ以上入れられますか？

## 回答

**別々のメッセージを、そのまま複数の引数として渡すことはできません。** `AuraHandledException`でLWCに渡す基本形は、1つの文字列メッセージです。ただし、2つ以上の文言を**1つの文字列にまとめて**渡すことはできます。

```apex
List<String> messages = new List<String>{
    '名前を入力してください。',
    'メールアドレスを確認してください。'
};
throw new AuraHandledException(String.join(messages, ' / '));
```

LWC側では、まとめた文言を1つのメッセージとして受け取ります。

```js
catch (error) {
    this.errorMessage = error?.body?.message || '入力を確認してください。';
}
```

**公式資料の該当箇所：** [Apex Exception Classの`AuraHandledException`](https://developer.salesforce.com/docs/platform/apex-ref/references/apex-ref/apex-classes-exception-methods.html)と、[LWC「Handle Errors from Apex」](https://developer.salesforce.com/docs/platform/lwc/guide/apex-error-handling.html)に、カスタムメッセージをJavaScript側へ返す用途が説明されています。複数文言を1つに結合する`String.join`は、[Apex String Classの`join(iterableObj, separator)`](https://developer.salesforce.com/docs/platform/apex-ref/references/apex-ref/apex-methods-system-string.html)に記載されています。

### Q. 2つの文言をLWC側で別々に扱いたい場合は？

その場合は、1つの文字列に結合するだけでは足りません。Apexの戻り値に`List<String>`を含むオブジェクトを用意し、LWCで配列として受け取る方法があります。ただし、この方法は**例外ではなく通常の戻り値**として結果を返す設計です。例外として返す必要がある場合は、メッセージにJSON文字列を入れてLWC側で解析する方法もありますが、受け取る側に追加処理が必要です。

**公式資料の該当箇所：** [LWC「Handle Errors from Apex」](https://developer.salesforce.com/docs/platform/lwc/guide/apex-error-handling.html)の「To return a custom error object instead, create a wrapper class」に、戻り値をオブジェクト化する方法があります。例外のメッセージにJSONを入れて解析する方法は、[Salesforce Developers Blog「Custom error handling」](https://developer.salesforce.com/blogs/2017/09/error-handling-best-practices-lightning-apex)に説明があります。このブログのコードはAura向けなので、LWCでは`error.body.message`から取り出す形に読み替えます。

なお、**`reduceErrors`に結合済みの1つのメッセージを渡しても、自動で元の2件に分けてはくれません。**
