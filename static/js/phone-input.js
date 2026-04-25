document.addEventListener("DOMContentLoaded", function () {
  const phoneInput = document.querySelector("#phone");

  if (phoneInput && window.intlTelInput) {
    const iti = window.intlTelInput(phoneInput, {
      initialCountry: "ng",
      separateDialCode: true,
      preferredCountries: ["ng", "us", "gb"]
    });

    const form = phoneInput.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        phoneInput.value = iti.getNumber();
      });
    }
  }
});